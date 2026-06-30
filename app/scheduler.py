"""APScheduler 기반 태스크 갱신 알림 스케줄러.

waitress 단일 프로세스 환경이라 인프로세스 스케줄러로 중복 발송이 없다.
1분마다 폴링하며, task_notify_enabled=1 인 프로젝트의 발송시각(HH:MM)이
지난 평일에 하루 1회 담당자별 메일을 발송한다.

시각 비교는 컨테이너 로컬시간(보통 UTC)이 아니라 config.APP_TZ(기본 Asia/Seoul)
기준으로 수행한다. 컨테이너가 UTC면 '09:00' 설정이 한국시간 18:00에 발송되는
문제를 막기 위함이다.
"""
import logging
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:  # py<3.9
    ZoneInfo = None

from flask import current_app

from apscheduler.schedulers.background import BackgroundScheduler

from app.extensions import get_db
from app.services import notification_service

logger = logging.getLogger(__name__)

# 발송 중복 방지: {date: set(project_id)}. 날짜가 바뀌면 정리된다.
_sent_today = {}
_scheduler = None       # 상태 조회용 스케줄러 인스턴스
_last_tick = None       # 마지막 폴링 시각 (작동 여부 판단용)


def _tz(tzname):
    if ZoneInfo:
        try:
            return ZoneInfo(tzname)
        except Exception:
            logger.warning("APP_TZ '%s' 해석 실패 — 시스템 로컬시간 사용", tzname)
    return None


def _now():
    """config.APP_TZ 기준 현재 시각 (tz 해석 실패 시 시스템 로컬)."""
    tzname = current_app.config.get('APP_TZ', 'Asia/Seoul')
    tz = _tz(tzname)
    return datetime.now(tz) if tz else datetime.now()


def init_scheduler(app):
    """앱에 백그라운드 스케줄러를 연결한다. 비활성 조건이면 None 반환."""
    global _scheduler
    if not _should_start(app):
        return None
    tz = _tz(app.config.get('APP_TZ', 'Asia/Seoul'))
    scheduler = BackgroundScheduler(daemon=True, timezone=tz) if tz else BackgroundScheduler(daemon=True)
    scheduler.add_job(lambda: _tick(app), 'interval', minutes=1, id='task_notify')
    scheduler.start()
    _scheduler = scheduler
    logger.info("태스크 알림 스케줄러 시작 (tz=%s)", app.config.get('APP_TZ', 'Asia/Seoul'))
    return scheduler


def _should_start(app):
    if app.config.get('TESTING'):
        return False
    if os.environ.get('ENABLE_SCHEDULER', '1') != '1':
        return False
    # Flask 개발 reloader의 부모 프로세스에서는 중복 기동을 막는다.
    if app.debug and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        return False
    return True


def _tick(app):
    global _last_tick
    with app.app_context():
        _last_tick = _now()
        try:
            _run_due_notifications()
        except Exception:
            logger.exception("태스크 알림 스케줄러 처리 오류")


def _run_due_notifications():
    now = _now()
    if now.weekday() >= 5:  # 토(5)/일(6) 제외 — 평일만
        return

    today = now.date()
    for d in list(_sent_today):  # 지난 날짜 정리
        if d != today:
            del _sent_today[d]
    sent = _sent_today.setdefault(today, set())

    cur_hm = now.strftime('%H:%M')
    db = get_db()
    rows = db.execute(
        "SELECT id, name, task_notify_time FROM project WHERE task_notify_enabled = 1"
    ).fetchall()

    for r in rows:
        pid = r['id']
        if pid in sent:
            continue
        target = (r['task_notify_time'] or '09:00')[:5]
        if cur_hm >= target:
            result = notification_service.send_task_update_mails(pid)
            sent.add(pid)  # 발송 시도 = 하루 1회 (재시도 폭주 방지)
            logger.info(
                "태스크 알림 발송 project=%s(%s) sent=%s/%s",
                pid, r['name'], result.get('sent'), result.get('total'),
            )


def get_status():
    """스케줄러 작동 상태를 반환한다 (admin 진단용)."""
    running = bool(_scheduler and _scheduler.running)
    next_run = None
    if _scheduler:
        job = _scheduler.get_job('task_notify')
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    return {
        'running': running,
        'tz': current_app.config.get('APP_TZ', 'Asia/Seoul'),
        'now': _now().isoformat(),
        'last_tick': _last_tick.isoformat() if _last_tick else None,
        'next_run': next_run,
        'sent_today': {str(d): sorted(s) for d, s in _sent_today.items()},
    }

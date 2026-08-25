"""APScheduler 기반 태스크 갱신 알림 스케줄러.

waitress 단일 프로세스 환경이라 인프로세스 스케줄러로 중복 발송이 없다.
1분마다 폴링하며, task_notify_enabled=1 인 프로젝트의 발송시각(HH:MM)이
지난 평일에 하루 1회 담당자별 메일을 발송한다.

시각 비교는 컨테이너 로컬시간(보통 UTC)이 아니라 config.APP_TZ(기본 Asia/Seoul)
기준으로 수행한다. 컨테이너가 UTC면 '09:00' 설정이 한국시간 18:00에 발송되는
문제를 막기 위함이다.

하루 1회 판정은 project.task_notify_last_date(DB)로 한다. 메모리 기록은 프로세스가
재기동되면 초기화되어, 발송시각이 지난 뒤 기동할 때마다 그날 메일을 다시 보냈다.
또한 발송시각을 _CATCHUP_MINUTES 이상 지난 뒤의 기동에서는 뒤늦은 발송을 하지 않는다.
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

# 발송시각을 놓친 뒤(서비스 중단 등) 뒤늦게 따라 보낼 수 있는 최대 지연(분).
# 이 창을 넘긴 기동에서는 그날 알림을 보내지 않고 처리 완료로 기록한다.
_CATCHUP_MINUTES = 120

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


def _to_minutes(hm):
    """'HH:MM' → 자정 기준 분. 형식이 잘못되면 None."""
    try:
        h, m = str(hm).split(':')[:2]
        return int(h) * 60 + int(m)
    except (TypeError, ValueError):
        return None


def _mark_done(db, project_id, today):
    """그날의 알림 처리 완료를 DB에 기록한다 (재기동 후에도 유지)."""
    db.execute(
        "UPDATE project SET task_notify_last_date = ? WHERE id = ?", (today, project_id)
    )
    db.commit()


def _run_due_notifications():
    now = _now()
    if now.weekday() >= 5:  # 토(5)/일(6) 제외 — 평일만
        return

    today = now.strftime('%Y-%m-%d')
    cur_min = now.hour * 60 + now.minute
    db = get_db()
    rows = db.execute(
        "SELECT id, name, task_notify_time, task_notify_last_date "
        "FROM project WHERE task_notify_enabled = 1"
    ).fetchall()

    for r in rows:
        pid = r['id']
        if (r['task_notify_last_date'] or '')[:10] == today:
            continue  # 오늘 이미 처리 — 재기동해도 다시 보내지 않는다
        target_min = _to_minutes((r['task_notify_time'] or '09:00')[:5])
        if target_min is None or cur_min < target_min:
            continue
        if cur_min - target_min > _CATCHUP_MINUTES:
            # 발송시각을 크게 지난 기동(예: 종일 중단 후 저녁 기동) — 뒤늦은 발송은 생략
            _mark_done(db, pid, today)
            logger.info(
                "태스크 알림 건너뜀(발송시각 경과) project=%s(%s) target=%s now=%s",
                pid, r['name'], r['task_notify_time'], now.strftime('%H:%M'),
            )
            continue
        _mark_done(db, pid, today)  # 발송 시도 = 하루 1회 (실패 시 재시도 폭주 방지)
        result = notification_service.send_task_update_mails(pid)
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
        'catchup_minutes': _CATCHUP_MINUTES,
        'done_today': _done_today_ids(),
    }


def _done_today_ids():
    """오늘 알림 처리(발송 또는 건너뜀)가 끝난 프로젝트 id 목록."""
    today = _now().strftime('%Y-%m-%d')
    rows = get_db().execute(
        "SELECT id FROM project WHERE substr(task_notify_last_date, 1, 10) = ?", (today,)
    ).fetchall()
    return [r['id'] for r in rows]

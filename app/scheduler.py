"""APScheduler 기반 태스크 갱신 알림 스케줄러.

waitress 단일 프로세스 환경이라 인프로세스 스케줄러로 중복 발송이 없다.
1분마다 폴링하며, task_notify_enabled=1 인 프로젝트의 발송시각(HH:MM)이
지난 평일에 하루 1회 담당자별 메일을 발송한다.
"""
import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.extensions import get_db
from app.services import notification_service

logger = logging.getLogger(__name__)

# 발송 중복 방지: {date: set(project_id)}. 날짜가 바뀌면 정리된다.
_sent_today = {}


def init_scheduler(app):
    """앱에 백그라운드 스케줄러를 연결한다. 비활성 조건이면 None 반환."""
    if not _should_start(app):
        return None
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(lambda: _tick(app), 'interval', minutes=1, id='task_notify')
    scheduler.start()
    logger.info("태스크 알림 스케줄러 시작")
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
    with app.app_context():
        try:
            _run_due_notifications()
        except Exception:
            logger.exception("태스크 알림 스케줄러 처리 오류")


def _run_due_notifications():
    now = datetime.now()
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

"""태스크 갱신 알림 — 설정 저장 / 이번주 필터 / 담당자별 발송 검증."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app import scheduler
from app.extensions import get_db
from app.services import notification_service


def _this_monday():
    today = date.today()
    return today - timedelta(days=today.weekday())


def test_project_persists_notify_settings(admin_client):
    """프로젝트 생성·수정 시 task_notify 설정이 저장된다."""
    created = admin_client.post('/api/projects', json={
        'name': 'NotifyProj',
        'task_notify_enabled': 1,
        'task_notify_time': '08:30',
    }).get_json()
    assert created['task_notify_enabled'] == 1
    assert created['task_notify_time'] == '08:30'

    pid = created['id']
    admin_client.put(f'/api/projects/{pid}', json={
        'task_notify_enabled': 0,
        'task_notify_time': '10:00',
    })
    fetched = admin_client.get(f'/api/projects/{pid}').get_json()
    assert fetched['task_notify_enabled'] == 0
    assert fetched['task_notify_time'] == '10:00'


def test_get_week_tasks_window_and_exclusions(app, admin_client):
    """이번주 겹침 포함 / 완료·윈도우 밖 제외."""
    pid = admin_client.post('/api/projects', json={'name': 'WeekTaskProj'}).get_json()['id']
    monday = _this_monday()

    def _add(**kw):
        admin_client.post(f'/api/wbs/{pid}/items', json=kw)

    _add(task_name='WK', subtask='이번주', assignee='가나',
         plan_start=str(monday + timedelta(days=1)), plan_end=str(monday + timedelta(days=2)), progress=30)
    _add(task_name='DONE', subtask='완료', assignee='가나',
         plan_start=str(monday), plan_end=str(monday + timedelta(days=1)), progress=100)
    _add(task_name='FUTURE', subtask='미래', assignee='가나',
         plan_start=str(monday + timedelta(days=40)), plan_end=str(monday + timedelta(days=45)), progress=0)

    with app.app_context():
        tasks = notification_service.get_week_tasks(pid)

    names = {t['subtask'] for t in tasks}
    assert '이번주' in names
    assert '완료' not in names
    assert '미래' not in names


def test_send_task_update_mails_groups_and_skips(app, admin_client, monkeypatch):
    """담당자별 발송 / 이메일 없는 담당자는 스킵 / 빈 목록은 미발송."""
    pid = admin_client.post('/api/projects', json={'name': 'SendProj'}).get_json()['id']
    monday = _this_monday()

    # TestAdmin(이메일 있음) + 이름만 있는 담당자(이메일 없음)
    admin_client.post(f'/api/wbs/{pid}/items', json={
        'task_name': 'A', 'assignee': 'TestAdmin',
        'plan_start': str(monday), 'plan_end': str(monday + timedelta(days=2)), 'progress': 10,
    })
    admin_client.post(f'/api/wbs/{pid}/items', json={
        'task_name': 'B', 'assignee': '이메일없음',
        'plan_start': str(monday), 'plan_end': str(monday + timedelta(days=2)), 'progress': 10,
    })

    calls = []
    monkeypatch.setattr(notification_service, 'send_html_mail',
                        lambda **kw: calls.append(kw) or (True, '발송 성공'))

    with app.app_context():
        result = notification_service.send_task_update_mails(pid, base_url='http://test.local')

    assert result['sent'] == 1                       # TestAdmin만 성공
    assert len(calls) == 1
    assert calls[0]['to_address'] == 'admin@test.local'
    assert '이번주 태스크' in calls[0]['subject']


def test_send_task_update_mail_endpoint(admin_client, viewer_client, monkeypatch):
    """즉시발송 엔드포인트: admin 발송 / viewer 차단."""
    from app.services import notification_service
    pid = admin_client.post('/api/projects', json={'name': 'NowProj'}).get_json()['id']

    monkeypatch.setattr(notification_service, 'send_html_mail', lambda **kw: (True, 'ok'))

    # viewer는 admin 권한 없어 차단
    resp_v = viewer_client.post(f'/api/wbs/{pid}/send-task-update-mail', json={})
    assert resp_v.status_code in (401, 403)

    # admin은 호출 가능 (할당 없으면 sent 0)
    resp = admin_client.post(f'/api/wbs/{pid}/send-task-update-mail', json={})
    assert resp.status_code == 200
    assert resp.get_json()['sent'] == 0


def test_scheduler_status_endpoint(admin_client, viewer_client):
    """스케줄러 상태 조회: admin 200 / viewer 차단. 테스트 환경은 미기동(running False)."""
    resp_v = viewer_client.get('/api/projects/scheduler/status')
    assert resp_v.status_code in (401, 403)

    resp = admin_client.get('/api/projects/scheduler/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['running'] is False           # TESTING이라 미기동
    assert data['tz'] == 'Asia/Seoul'
    assert 'now' in data and 'last_tick' in data


def test_send_task_update_mails_empty_no_send(app, admin_client, monkeypatch):
    """이번주 할당 태스크가 없으면 메일을 보내지 않는다."""
    pid = admin_client.post('/api/projects', json={'name': 'EmptyProj'}).get_json()['id']
    calls = []
    monkeypatch.setattr(notification_service, 'send_html_mail',
                        lambda **kw: calls.append(kw) or (True, 'ok'))

    with app.app_context():
        result = notification_service.send_task_update_mails(pid, base_url='http://test.local')

    assert result['sent'] == 0
    assert calls == []


def _weekday_at(hour, minute):
    """이번주 월요일의 지정 시각 (평일 고정)."""
    monday = _this_monday()
    return datetime(monday.year, monday.month, monday.day, hour, minute)


def _notify_project(admin_client, name, notify_time):
    return admin_client.post('/api/projects', json={
        'name': name, 'task_notify_enabled': 1, 'task_notify_time': notify_time,
    }).get_json()['id']


def _last_date(app, pid):
    with app.app_context():
        return get_db().execute(
            "SELECT task_notify_last_date FROM project WHERE id = ?", (pid,)
        ).fetchone()['task_notify_last_date']


def test_scheduler_sends_once_per_day(app, admin_client, monkeypatch):
    """발송시각이 지나면 1회 발송하고 날짜를 DB에 기록한다.

    하루 1회 판정이 DB(task_notify_last_date) 기준이므로, 프로세스가 재기동되어
    모듈 상태가 초기화되어도(= 아래 두 번째 호출) 같은 날 다시 보내지 않는다.
    """
    pid = _notify_project(admin_client, 'SchedOnce', '09:00')
    calls = []
    monkeypatch.setattr(scheduler.notification_service, 'send_task_update_mails',
                        lambda p: calls.append(p) or {'sent': 1, 'total': 1})
    monkeypatch.setattr(scheduler, '_now', lambda: _weekday_at(9, 30))

    with app.app_context():
        scheduler._run_due_notifications()
    assert calls == [pid]
    assert _last_date(app, pid) == _this_monday().strftime('%Y-%m-%d')

    with app.app_context():
        scheduler._run_due_notifications()
    assert calls == [pid]   # 재기동/재폴링에도 추가 발송 없음


def test_scheduler_skips_before_target_time(app, admin_client, monkeypatch):
    """발송시각 전에는 보내지 않고 기록도 남기지 않는다."""
    pid = _notify_project(admin_client, 'SchedEarly', '09:00')
    calls = []
    monkeypatch.setattr(scheduler.notification_service, 'send_task_update_mails',
                        lambda p: calls.append(p) or {'sent': 1, 'total': 1})
    monkeypatch.setattr(scheduler, '_now', lambda: _weekday_at(8, 59))

    with app.app_context():
        scheduler._run_due_notifications()
    assert calls == []
    assert _last_date(app, pid) is None


def test_scheduler_skips_late_startup(app, admin_client, monkeypatch):
    """발송시각을 크게 지난 기동은 뒤늦게 보내지 않고 처리 완료로 기록한다."""
    pid = _notify_project(admin_client, 'SchedLate', '09:00')
    calls = []
    monkeypatch.setattr(scheduler.notification_service, 'send_task_update_mails',
                        lambda p: calls.append(p) or {'sent': 1, 'total': 1})
    monkeypatch.setattr(scheduler, '_now', lambda: _weekday_at(18, 40))

    with app.app_context():
        scheduler._run_due_notifications()
    assert calls == []
    assert _last_date(app, pid) == _this_monday().strftime('%Y-%m-%d')


def test_scheduler_skips_weekend(app, admin_client, monkeypatch):
    """주말에는 발송하지 않는다."""
    pid = _notify_project(admin_client, 'SchedWeekend', '09:00')
    calls = []
    monkeypatch.setattr(scheduler.notification_service, 'send_task_update_mails',
                        lambda p: calls.append(p) or {'sent': 1, 'total': 1})
    saturday = _this_monday() + timedelta(days=5)
    monkeypatch.setattr(scheduler, '_now',
                        lambda: datetime(saturday.year, saturday.month, saturday.day, 10, 0))

    with app.app_context():
        scheduler._run_due_notifications()
    assert calls == []
    assert _last_date(app, pid) is None

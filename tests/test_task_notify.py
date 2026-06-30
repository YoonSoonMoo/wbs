"""태스크 갱신 알림 — 설정 저장 / 이번주 필터 / 담당자별 발송 검증."""
from __future__ import annotations

from datetime import date, timedelta

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

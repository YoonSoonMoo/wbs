"""5단계 권한(admin/pm/pl/developer/viewer) 및 계획일자 수정 제한 테스트."""
import pytest

from app.services import auth_service


def _mk_user(app, name, email):
    with app.app_context():
        return auth_service.register_user(name, email, 'pw1234', role='developer')


def _client(app, email):
    c = app.test_client()
    c.post('/login', data={'email': email, 'password': 'pw1234'})
    return c


@pytest.fixture
def roles_project(app, admin_client):
    """pm/pl/developer/viewer 멤버가 각각 배정된 프로젝트 + 역할별 클라이언트."""
    pm_id = _mk_user(app, 'pm1', 'pm@test.local')
    pl_id = _mk_user(app, 'pl1', 'pl@test.local')
    dev_id = _mk_user(app, 'dev2', 'dev2@test.local')
    view_id = _mk_user(app, 'view2', 'view2@test.local')
    resp = admin_client.post('/api/projects', json={
        'name': '역할 프로젝트',
        'members': [
            {'user_id': pm_id, 'role': 'pm'},
            {'user_id': pl_id, 'role': 'pl'},
            {'user_id': dev_id, 'role': 'developer'},
            {'user_id': view_id, 'role': 'viewer'},
        ],
    })
    assert resp.status_code == 201, resp.data
    return {
        'pid': resp.get_json()['id'],
        'admin': admin_client,
        'pm': _client(app, 'pm@test.local'),
        'pl': _client(app, 'pl@test.local'),
        'dev': _client(app, 'dev2@test.local'),
        'view': _client(app, 'view2@test.local'),
    }


def _new_item(client, pid):
    resp = client.post(f'/api/wbs/{pid}/items', json={
        'task_name': 't', 'plan_start': '2026-04-01', 'plan_end': '2026-04-10',
    })
    assert resp.status_code == 201, resp.data
    return resp.get_json()['id']


# ── 프로젝트별 역할 저장/조회 ──

def test_project_member_roles_stored(app, roles_project):
    with app.app_context():
        from app.services.auth_service import get_project_members
        members = {m['name']: m['role'] for m in get_project_members(roles_project['pid'])}
    assert members['pm1'] == 'pm'
    assert members['pl1'] == 'pl'
    assert members['dev2'] == 'developer'
    assert members['view2'] == 'viewer'


# ── 프로젝트 수정: admin/PM 가능, PL/developer 불가 ──

@pytest.mark.parametrize('who,expected', [('admin', 200), ('pm', 200), ('pl', 403), ('dev', 403), ('view', 403)])
def test_project_update_permission(roles_project, who, expected):
    resp = roles_project[who].put(f"/api/projects/{roles_project['pid']}", json={'name': '변경'})
    assert resp.status_code == expected


# ── 프로젝트 삭제/초기화: admin/PM 가능, 그 외 불가 ──

@pytest.mark.parametrize('who,expected', [('pm', 200), ('pl', 403), ('dev', 403)])
def test_clear_items_permission(roles_project, who, expected):
    resp = roles_project[who].delete(f"/api/wbs/{roles_project['pid']}/items")
    assert resp.status_code == expected


# ── 메일 발송: admin/PM 가능, PL/developer 불가 ──

@pytest.mark.parametrize('who,forbidden', [('pm', False), ('pl', True), ('dev', True)])
def test_send_delay_mail_permission(roles_project, who, forbidden):
    resp = roles_project[who].post(f"/api/wbs/{roles_project['pid']}/send-delay-mail", json={})
    if forbidden:
        assert resp.status_code == 403
    else:
        assert resp.status_code == 200  # 지연 항목 없으면 sent:0 으로 200


# ── AI 어시스턴트: admin/PM/PL 가능, developer/viewer 불가 ──

@pytest.mark.parametrize('who,forbidden', [('pm', False), ('pl', False), ('dev', True), ('view', True)])
def test_ai_permission(roles_project, monkeypatch, who, forbidden):
    monkeypatch.setattr('app.routes.api_wbs.ai_process_command',
                        lambda pid, q: {'success': True, 'action': 'query', 'ids': [], 'display': ''})
    resp = roles_project[who].post(f"/api/wbs/{roles_project['pid']}/ai", json={'query': '조회'})
    assert (resp.status_code == 403) == forbidden


# ── 계획시작/계획완료 수정 제한 ──

def test_developer_cannot_edit_plan_dates(roles_project):
    pid = roles_project['pid']
    item_id = _new_item(roles_project['admin'], pid)
    resp = roles_project['dev'].patch(f'/api/wbs/items/{item_id}', json={'plan_start': '2026-05-01'})
    assert resp.status_code == 403
    assert 'PM/PL' in resp.get_json()['error']


def test_developer_can_edit_other_fields(roles_project):
    pid = roles_project['pid']
    item_id = _new_item(roles_project['admin'], pid)
    resp = roles_project['dev'].patch(f'/api/wbs/items/{item_id}', json={'assignee': '홍길동'})
    assert resp.status_code == 200


@pytest.mark.parametrize('who', ['pl', 'pm', 'admin'])
def test_planner_can_edit_plan_dates(roles_project, who):
    pid = roles_project['pid']
    item_id = _new_item(roles_project['admin'], pid)
    resp = roles_project[who].patch(f'/api/wbs/items/{item_id}', json={'plan_end': '2026-05-20'})
    assert resp.status_code == 200


def test_developer_batch_plan_dates_ignored(roles_project):
    """developer 일괄수정 시 계획일자 변경은 무시되고 나머지는 반영된다."""
    pid = roles_project['pid']
    item_id = _new_item(roles_project['admin'], pid)
    resp = roles_project['dev'].post(f'/api/wbs/{pid}/items/batch', json={
        'items': [{'id': item_id, 'plan_end': '2026-09-09', 'assignee': '김개발'}],
    })
    assert resp.status_code == 200
    got = roles_project['dev'].get(f'/api/wbs/items/{item_id}').get_json()
    assert got['assignee'] == '김개발'      # 일반 필드는 반영
    assert got['plan_end'] == '2026-04-10'  # 계획일자는 그대로


# ── PM은 멤버 추가/삭제 + 역할 지정까지 가능 (멤버 관리 전권) ──

def test_pm_can_manage_members(app, roles_project):
    pid = roles_project['pid']
    with app.app_context():
        from app.services.auth_service import get_project_members
        members = get_project_members(pid)
    # PM이 dev2를 pl로 승격 (나머지는 유지)
    payload = [{'user_id': m['id'], 'role': ('pl' if m['name'] == 'dev2' else m['role'])} for m in members]
    resp = roles_project['pm'].put(f'/api/projects/{pid}', json={'name': 'PM수정', 'members': payload})
    assert resp.status_code == 200
    with app.app_context():
        from app.services.auth_service import get_project_members
        roles = {m['name']: m['role'] for m in get_project_members(pid)}
    assert roles['dev2'] == 'pl'   # PM이 역할 변경 성공
    assert len(roles) == 4         # 멤버 수 유지


def test_pl_cannot_manage_members(app, roles_project):
    """PL은 프로젝트 수정 권한이 없으므로 멤버 변경도 불가(403)."""
    pid = roles_project['pid']
    resp = roles_project['pl'].put(f'/api/projects/{pid}', json={'name': 'x', 'members': []})
    assert resp.status_code == 403

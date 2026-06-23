"""API 토큰 인증 테스트.

세션 없이 Authorization: Bearer <token> 헤더만으로 인증/권한이 동작하는지,
그리고 관리자 발급 엔드포인트가 토큰을 이메일로 전송하는지 검증한다.
(Claude CLI 등 외부 클라이언트의 WBS 갱신 시나리오)
"""
from __future__ import annotations

from app.services import auth_service


def _make_token(app, user_id):
    """테스트용으로 평문 토큰을 직접 발급한다(이메일 경로 우회)."""
    with app.app_context():
        return auth_service.generate_api_token(user_id)


def _admin_id(admin_client):
    with admin_client.session_transaction() as sess:
        return sess['user_id']


def _bearer(token):
    return {'Authorization': f'Bearer {token}'}


# --- 인증 동작 ---

def test_me_with_token(app, admin_client, anonymous_client):
    token = _make_token(app, _admin_id(admin_client))
    resp = anonymous_client.get('/api/users/me', headers=_bearer(token))
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    assert body['name'] == 'TestAdmin'
    assert body['role'] == 'admin'


def test_me_without_auth_is_401(anonymous_client):
    assert anonymous_client.get('/api/users/me').status_code == 401


def test_invalid_token_is_401(anonymous_client):
    resp = anonymous_client.get('/api/users/me', headers=_bearer('not-a-real-token'))
    assert resp.status_code == 401


def test_token_can_read_and_patch_items(app, admin_client, project_id, wbs_item, anonymous_client):
    token = _make_token(app, _admin_id(admin_client))

    resp = anonymous_client.get(f'/api/wbs/{project_id}/items', headers=_bearer(token))
    assert resp.status_code == 200, resp.data

    resp = anonymous_client.patch(
        f'/api/wbs/items/{wbs_item}',
        json={'progress': 60, 'status': '진행중'},
        headers=_bearer(token),
    )
    assert resp.status_code == 200, resp.data
    assert resp.get_json()['progress'] == 60


def test_developer_token_can_patch_member_project(
    app, developer_user, project_with_members, anonymous_client
):
    token = _make_token(app, developer_user)
    resp = anonymous_client.post(
        f'/api/wbs/{project_with_members}/items',
        json={'task_name': '토큰 생성 태스크', 'category': '개발'},
        headers=_bearer(token),
    )
    assert resp.status_code == 201, resp.data


def test_viewer_token_cannot_write(app, viewer_user, project_with_members, anonymous_client):
    token = _make_token(app, viewer_user)
    resp = anonymous_client.post(
        f'/api/wbs/{project_with_members}/items',
        json={'task_name': '거부되어야 함'},
        headers=_bearer(token),
    )
    assert resp.status_code == 403, resp.data


# --- 관리자 발급 엔드포인트 ---

def test_admin_issues_token_via_email(admin_client, developer_user, anonymous_client, monkeypatch):
    captured = {}

    def _fake_mail(to_address, to_name, subject, html_body):
        captured['html'] = html_body
        captured['to'] = to_address
        return (True, 'mocked')

    import app.routes.api_users as users_route
    monkeypatch.setattr(users_route, 'send_html_mail', _fake_mail)

    resp = admin_client.post(f'/api/users/{developer_user}/api-token')
    assert resp.status_code == 200, resp.data
    assert resp.get_json() == {'ok': True}
    assert captured['to'] == 'dev@test.local'

    # 이메일 본문에서 토큰을 추출해 실제로 인증되는지 확인
    token = captured['html'].split('<strong>')[1].split('</strong>')[0]
    me = anonymous_client.get('/api/users/me', headers=_bearer(token))
    assert me.status_code == 200
    assert me.get_json()['name'] == 'dev1'


def test_issue_token_requires_admin(developer_client, viewer_user):
    resp = developer_client.post(f'/api/users/{viewer_user}/api-token')
    assert resp.status_code == 403


def test_issue_token_user_not_found(admin_client):
    resp = admin_client.post('/api/users/99999/api-token')
    assert resp.status_code == 404


def test_admin_revokes_token(app, admin_client, developer_user, anonymous_client):
    token = _make_token(app, developer_user)
    assert anonymous_client.get('/api/users/me', headers=_bearer(token)).status_code == 200

    resp = admin_client.delete(f'/api/users/{developer_user}/api-token')
    assert resp.status_code == 200
    assert anonymous_client.get('/api/users/me', headers=_bearer(token)).status_code == 401

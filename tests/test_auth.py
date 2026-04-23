"""/login, /register, /logout 및 /api/users/me/password 흐름 테스트."""
from __future__ import annotations


from tests.conftest import ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD


def test_login_success_redirects_to_index(client, app):
    resp = client.post(
        '/login',
        data={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess['user_role'] == 'admin'
        assert sess['user_name'] == ADMIN_NAME


def test_login_wrong_password(client, app):
    resp = client.post(
        '/login',
        data={'email': ADMIN_EMAIL, 'password': 'wrong'},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_inactive_user_blocked(client, app, viewer_user):
    from app.services import auth_service
    with app.app_context():
        auth_service.set_user_active(viewer_user, False)

    resp = client.post(
        '/login',
        data={'email': 'view@test.local', 'password': 'pw1234'},
        follow_redirects=False,
    )
    with client.session_transaction() as sess:
        assert 'user_id' not in sess
    assert resp.status_code == 200


def test_register_creates_viewer(client, app):
    resp = client.post(
        '/register',
        data={
            'name': 'newbie',
            'email': 'newbie@test.local',
            'password': 'pw1234',
            'password_confirm': 'pw1234',
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    from app.services import auth_service
    with app.app_context():
        users = {u['email']: u for u in auth_service.get_all_users()}
        assert 'newbie@test.local' in users
        assert users['newbie@test.local']['role'] == 'viewer'


def test_register_password_mismatch(client):
    resp = client.post(
        '/register',
        data={
            'name': 'bob',
            'email': 'bob@test.local',
            'password': 'aaaa',
            'password_confirm': 'bbbb',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200


def test_logout_clears_session(admin_client):
    admin_client.get('/logout', follow_redirects=False)
    with admin_client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_change_my_password_too_short(developer_client):
    resp = developer_client.put('/api/users/me/password', json={'password': '12'})
    assert resp.status_code == 400


def test_change_my_password_ok_and_relogin(app, developer_client):
    resp = developer_client.put('/api/users/me/password', json={'password': 'newpw123'})
    assert resp.status_code == 200

    c2 = app.test_client()
    resp = c2.post(
        '/login',
        data={'email': 'dev@test.local', 'password': 'newpw123'},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with c2.session_transaction() as sess:
        assert sess['user_role'] == 'developer'


def test_api_requires_login(anonymous_client):
    resp = anonymous_client.get('/api/projects')
    assert resp.status_code == 401

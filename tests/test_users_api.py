"""/api/users 엔드포인트 테스트."""
from __future__ import annotations

import pytest


def test_list_users_requires_admin(developer_client):
    resp = developer_client.get('/api/users')
    assert resp.status_code == 403


def test_list_users_as_admin(admin_client, developer_user, viewer_user):
    resp = admin_client.get('/api/users')
    assert resp.status_code == 200
    emails = {u['email'] for u in resp.get_json()}
    assert 'admin@test.local' in emails
    assert 'dev@test.local' in emails
    assert 'view@test.local' in emails


def test_update_role_valid(admin_client, viewer_user):
    resp = admin_client.put(f'/api/users/{viewer_user}/role', json={'role': 'developer'})
    assert resp.status_code == 200
    users = admin_client.get('/api/users').get_json()
    changed = next(u for u in users if u['id'] == viewer_user)
    assert changed['role'] == 'developer'


def test_update_role_invalid(admin_client, viewer_user):
    resp = admin_client.put(f'/api/users/{viewer_user}/role', json={'role': 'superuser'})
    assert resp.status_code == 400


def test_set_active_toggle(admin_client, developer_user):
    resp = admin_client.put(f'/api/users/{developer_user}/active', json={'is_active': False})
    assert resp.status_code == 200
    users = admin_client.get('/api/users').get_json()
    row = next(u for u in users if u['id'] == developer_user)
    assert row['is_active'] == 0


def test_cannot_deactivate_self(admin_client, app):
    # admin 자신의 id 조회
    with admin_client.session_transaction() as sess:
        admin_id = sess['user_id']
    resp = admin_client.put(f'/api/users/{admin_id}/active', json={'is_active': False})
    assert resp.status_code == 400


def test_reset_password(admin_client, developer_user, monkeypatch):
    # 메일 발송 외부호출 방지
    import app.routes.api_users as users_route
    monkeypatch.setattr(users_route, 'send_html_mail', lambda *a, **kw: (True, 'mocked'))

    resp = admin_client.post(f'/api/users/{developer_user}/reset-password')
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}


def test_reset_password_user_not_found(admin_client, monkeypatch):
    import app.routes.api_users as users_route
    monkeypatch.setattr(users_route, 'send_html_mail', lambda *a, **kw: (True, 'mocked'))
    resp = admin_client.post('/api/users/99999/reset-password')
    assert resp.status_code == 404

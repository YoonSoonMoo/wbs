"""/api/projects 엔드포인트 테스트."""
from __future__ import annotations


def test_create_project_as_admin(admin_client):
    resp = admin_client.post(
        '/api/projects',
        json={'name': '신규', 'description': '설명'},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['name'] == '신규'
    assert body['id']


def test_create_project_requires_name(admin_client):
    resp = admin_client.post('/api/projects', json={'description': '이름 없음'})
    assert resp.status_code == 400


def test_create_project_forbidden_for_developer(developer_client):
    resp = developer_client.post('/api/projects', json={'name': 'X'})
    assert resp.status_code == 403


def test_list_projects_admin_sees_all(admin_client, project_id):
    resp = admin_client.get('/api/projects')
    assert resp.status_code == 200
    names = [p['name'] for p in resp.get_json()]
    assert '테스트 프로젝트' in names


def test_list_projects_non_admin_only_member(admin_client, app, developer_user, viewer_user):
    # 두 개 프로젝트 중 한 개에만 dev 를 멤버로 추가
    p1 = admin_client.post('/api/projects', json={'name': 'P1',
            'members': [{'user_id': developer_user, 'role': 'developer'}]}).get_json()['id']
    p2 = admin_client.post('/api/projects', json={'name': 'P2'}).get_json()['id']

    c = app.test_client()
    c.post('/login', data={'email': 'dev@test.local', 'password': 'pw1234'})
    resp = c.get('/api/projects')
    assert resp.status_code == 200
    ids = {p['id'] for p in resp.get_json()}
    assert p1 in ids
    assert p2 not in ids


def test_get_project(admin_client, project_id):
    resp = admin_client.get(f'/api/projects/{project_id}')
    assert resp.status_code == 200
    assert resp.get_json()['id'] == project_id


def test_get_project_not_found(admin_client):
    resp = admin_client.get('/api/projects/99999')
    assert resp.status_code == 404


def test_update_project(admin_client, project_id):
    resp = admin_client.put(
        f'/api/projects/{project_id}',
        json={'name': '변경됨', 'description': '업데이트'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['name'] == '변경됨'


def test_update_project_developer_forbidden(developer_client, admin_client, project_id, developer_user):
    # dev 를 멤버로 등록해도 프로젝트 수정은 admin 만 가능
    admin_client.put(
        f'/api/projects/{project_id}',
        json={'members': [{'user_id': developer_user, 'role': 'developer'}]},
    )
    resp = developer_client.put(f'/api/projects/{project_id}', json={'name': 'X'})
    assert resp.status_code == 403


def test_delete_project(admin_client, project_id):
    resp = admin_client.delete(f'/api/projects/{project_id}')
    assert resp.status_code == 200
    assert admin_client.get(f'/api/projects/{project_id}').status_code == 404


def test_project_members_roundtrip(admin_client, project_id, developer_user):
    admin_client.put(
        f'/api/projects/{project_id}',
        json={'members': [{'user_id': developer_user, 'role': 'developer'}]},
    )
    resp = admin_client.get(f'/api/projects/{project_id}/members')
    assert resp.status_code == 200
    members = resp.get_json()
    assert any(m['id'] == developer_user and m['role'] == 'developer' for m in members)


def test_users_sub_endpoint(admin_client, developer_user):
    resp = admin_client.get('/api/projects/users')
    assert resp.status_code == 200
    emails = {u['email'] for u in resp.get_json()}
    assert 'dev@test.local' in emails

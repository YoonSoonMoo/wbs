"""/api/wbs 엔드포인트 테스트."""
from __future__ import annotations


# --- CRUD ---

def test_create_item(admin_client, project_id):
    resp = admin_client.post(
        f'/api/wbs/{project_id}/items',
        json={'task_name': '새 항목', 'category': '분석'},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['task_name'] == '새 항목'
    assert body['project_id'] == project_id
    # WBS 코드가 재계산되어 들어간다
    assert body['wbs_code'] != ''


def test_create_item_no_body(admin_client, project_id):
    resp = admin_client.post(f'/api/wbs/{project_id}/items', json={})
    assert resp.status_code == 400


def test_list_items_flat(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/wbs/{project_id}/items')
    assert resp.status_code == 200
    items = resp.get_json()
    assert any(i['id'] == wbs_item for i in items)


def test_list_items_tree(admin_client, project_id, wbs_item):
    # 자식 항목 생성
    child_resp = admin_client.post(
        f'/api/wbs/{project_id}/items',
        json={'task_name': '자식', 'parent_id': wbs_item},
    )
    assert child_resp.status_code == 201

    resp = admin_client.get(f'/api/wbs/{project_id}/items?mode=tree')
    assert resp.status_code == 200
    roots = resp.get_json()
    root = next(r for r in roots if r['id'] == wbs_item)
    assert len(root['children']) == 1
    assert root['children'][0]['task_name'] == '자식'


def test_get_item_not_found(admin_client):
    resp = admin_client.get('/api/wbs/items/99999')
    assert resp.status_code == 404


def test_update_item_put(admin_client, wbs_item):
    resp = admin_client.put(
        f'/api/wbs/items/{wbs_item}',
        json={'task_name': '수정됨', 'progress': 50},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['task_name'] == '수정됨'
    assert body['progress'] == 50


def test_patch_item(admin_client, wbs_item):
    resp = admin_client.patch(f'/api/wbs/items/{wbs_item}', json={'progress': 100})
    assert resp.status_code == 200
    assert resp.get_json()['progress'] == 100


def test_delete_item(admin_client, project_id, wbs_item):
    resp = admin_client.delete(f'/api/wbs/items/{wbs_item}')
    assert resp.status_code == 200
    assert admin_client.get(f'/api/wbs/items/{wbs_item}').status_code == 404


def test_update_item_empty_payload(admin_client, wbs_item):
    resp = admin_client.put(f'/api/wbs/items/{wbs_item}', json={})
    assert resp.status_code == 400


# --- 권한 ---

def test_viewer_cannot_create_item(admin_client, viewer_user, app):
    # admin 이 만든 프로젝트에 viewer 를 뷰어로 추가
    proj = admin_client.post('/api/projects', json={
        'name': 'P', 'members': [{'user_id': viewer_user, 'role': 'viewer'}],
    }).get_json()['id']

    c = app.test_client()
    c.post('/login', data={'email': 'view@test.local', 'password': 'pw1234'})
    resp = c.post(f'/api/wbs/{proj}/items', json={'task_name': 'X'})
    assert resp.status_code == 403


def test_non_member_cannot_read_items(admin_client, project_id, app, viewer_user):
    # viewer 는 이 프로젝트의 멤버가 아님
    c = app.test_client()
    c.post('/login', data={'email': 'view@test.local', 'password': 'pw1234'})
    resp = c.get(f'/api/wbs/{project_id}/items')
    assert resp.status_code == 403


def test_viewer_cannot_update_item(admin_client, viewer_user, app):
    # viewer 를 뷰어로 등록한 프로젝트
    proj = admin_client.post('/api/projects', json={
        'name': 'P', 'members': [{'user_id': viewer_user, 'role': 'viewer'}],
    }).get_json()['id']
    item = admin_client.post(
        f'/api/wbs/{proj}/items', json={'task_name': '부모'}
    ).get_json()['id']

    c = app.test_client()
    c.post('/login', data={'email': 'view@test.local', 'password': 'pw1234'})
    resp = c.put(f'/api/wbs/items/{item}', json={'task_name': '바꿈'})
    assert resp.status_code == 403


# --- 배치 / 이동 / 초기화 ---

def test_batch_update(admin_client, project_id, wbs_item):
    # 두 번째 항목 추가
    second = admin_client.post(
        f'/api/wbs/{project_id}/items', json={'task_name': '두번째'}
    ).get_json()['id']

    resp = admin_client.post(
        f'/api/wbs/{project_id}/items/batch',
        json={'items': [
            {'id': wbs_item, 'progress': 80},
            {'id': second, 'progress': 40},
        ]},
    )
    assert resp.status_code == 200
    result = resp.get_json()
    by_id = {r['id']: r for r in result}
    assert by_id[wbs_item]['progress'] == 80
    assert by_id[second]['progress'] == 40


def test_batch_update_requires_items_list(admin_client, project_id):
    resp = admin_client.post(f'/api/wbs/{project_id}/items/batch', json={})
    assert resp.status_code == 400


def test_move_item_reorders(admin_client, project_id, wbs_item):
    other = admin_client.post(
        f'/api/wbs/{project_id}/items', json={'task_name': '두번째'}
    ).get_json()['id']

    # wbs_item 을 두번째 위치로 이동
    resp = admin_client.post(
        f'/api/wbs/items/{wbs_item}/move',
        json={'parent_id': None, 'sort_order': 1},
    )
    assert resp.status_code == 200

    items = admin_client.get(f'/api/wbs/{project_id}/items').get_json()
    by_id = {i['id']: i for i in items}
    assert by_id[wbs_item]['sort_order'] == 1
    assert by_id[other]['sort_order'] == 0


def test_clear_all_items(admin_client, project_id, wbs_item):
    admin_client.post(f'/api/wbs/{project_id}/items', json={'task_name': 'extra'})
    resp = admin_client.delete(f'/api/wbs/{project_id}/items')
    assert resp.status_code == 200

    items = admin_client.get(f'/api/wbs/{project_id}/items').get_json()
    assert items == []


# --- 통계 / 대시보드 ---

def test_stats_shape(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/wbs/{project_id}/stats')
    assert resp.status_code == 200
    stats = resp.get_json()
    for key in ('total', 'completed', 'in_progress', 'not_started', 'delayed', 'avg_progress'):
        assert key in stats
    assert stats['total'] >= 1


def test_weekly_stats_shape(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/wbs/{project_id}/weekly-stats?weeks=4')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'overview' in data
    assert 'weekly' in data
    assert isinstance(data['weekly'], list)
    assert data['weekly'][0]['is_current'] is True


def test_weekly_stats_clamps_weeks(admin_client, project_id):
    # 26주 상한
    resp = admin_client.get(f'/api/wbs/{project_id}/weekly-stats?weeks=999')
    assert resp.status_code == 200
    weeks = resp.get_json()['weekly']
    assert len(weeks) == 26 + 1  # 이번 주 + 과거 26주


def test_dashboard_shape(admin_client, project_id, wbs_item):
    resp = admin_client.get(f'/api/wbs/{project_id}/dashboard')
    assert resp.status_code == 200
    body = resp.get_json()
    for key in ('overview', 'by_category', 'by_assignee', 'timeline'):
        assert key in body


def test_delayed_endpoint(admin_client, project_id, wbs_item):
    # 이미 지나간 plan_end + 진척 50% → 지연 항목
    admin_client.patch(
        f'/api/wbs/items/{wbs_item}',
        json={'plan_end': '2020-01-01', 'progress': 50},
    )
    resp = admin_client.get(f'/api/wbs/{project_id}/delayed')
    assert resp.status_code == 200
    ids = [i['id'] for i in resp.get_json()]
    assert wbs_item in ids


def test_schedule_gaps_endpoint(admin_client, project_id, wbs_item):
    admin_client.patch(
        f'/api/wbs/items/{wbs_item}',
        json={'plan_end': '2026-01-10', 'actual_end': '2026-01-20'},
    )
    resp = admin_client.get(f'/api/wbs/{project_id}/schedule-gaps')
    assert resp.status_code == 200
    # 응답 형식은 분석 결과(dict)
    assert resp.get_json() is not None


# --- AI 어시스턴트 ---

def test_ai_requires_query(admin_client, project_id, monkeypatch):
    import app.routes.api_wbs as wbs_route
    monkeypatch.setattr(wbs_route, 'ai_process_command', lambda *a, **kw: {'success': True, 'action': 'query'})
    resp = admin_client.post(f'/api/wbs/{project_id}/ai', json={'query': ''})
    assert resp.status_code == 400


def test_ai_happy_path(admin_client, project_id, monkeypatch):
    import app.routes.api_wbs as wbs_route
    monkeypatch.setattr(
        wbs_route,
        'ai_process_command',
        lambda *a, **kw: {'success': True, 'action': 'query', 'message': 'ok'},
    )
    resp = admin_client.post(f'/api/wbs/{project_id}/ai', json={'query': '요약'})
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

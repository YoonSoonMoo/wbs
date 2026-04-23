"""주간 통계의 전체 진척률(공수 기준) 계산 검증."""
from __future__ import annotations

from app.services import wbs_service


def test_round_half_up_1():
    # 사사오입: 0.05 → 0.1 (뱅커즈 라운딩이면 0.0)
    assert wbs_service._round_half_up_1(0.05) == 0.1
    assert wbs_service._round_half_up_1(0.15) == 0.2
    assert wbs_service._round_half_up_1(0.14) == 0.1
    assert wbs_service._round_half_up_1(85.25) == 85.3
    assert wbs_service._round_half_up_1(85.24) == 85.2
    assert wbs_service._round_half_up_1(0) == 0.0
    assert wbs_service._round_half_up_1(None) == 0.0


def _create(admin_client, project_id, effort, progress):
    return admin_client.post(f'/api/wbs/{project_id}/items', json={
        'task_name': f'e{effort}p{progress}',
        'effort': effort,
        'progress': progress,
    }).get_json()['id']


def test_overview_progress_rate_is_effort_based(admin_client, project_id):
    # 공수 10 완료(100%) + 공수 20 미완료(50%) → 완료 공수=10, 전체 공수=30
    # 태스크 기준: 1/2 = 50.0%
    # 공수 기준: 10/30 * 100 = 33.333... → 33.3%
    _create(admin_client, project_id, effort=10, progress=100)
    _create(admin_client, project_id, effort=20, progress=50)

    resp = admin_client.get(f'/api/wbs/{project_id}/weekly-stats')
    assert resp.status_code == 200
    ov = resp.get_json()['overview']
    assert ov['total'] == 2
    assert ov['completed'] == 1
    assert ov['total_effort'] == 30.0
    assert ov['completed_effort'] == 10.0
    assert ov['progress_rate'] == 33.3


def test_overview_progress_rate_half_up_at_second_decimal(admin_client, project_id):
    # 완료 1 / 전체 8 → 12.5% 정확히 (0.125 * 100)
    _create(admin_client, project_id, effort=1, progress=100)
    _create(admin_client, project_id, effort=7, progress=0)
    ov = admin_client.get(f'/api/wbs/{project_id}/weekly-stats').get_json()['overview']
    assert ov['progress_rate'] == 12.5

    # 완료 3 / 전체 7 → 42.857... → 42.9
    from app.extensions import get_db
    # 기존 항목 제거 후 재구성
    admin_client.delete(f'/api/wbs/{project_id}/items')
    _create(admin_client, project_id, effort=3, progress=100)
    _create(admin_client, project_id, effort=4, progress=0)
    ov = admin_client.get(f'/api/wbs/{project_id}/weekly-stats').get_json()['overview']
    assert ov['progress_rate'] == 42.9


def test_overview_progress_rate_zero_effort(admin_client, project_id):
    # effort 모두 0 → 0.0
    _create(admin_client, project_id, effort=0, progress=100)
    ov = admin_client.get(f'/api/wbs/{project_id}/weekly-stats').get_json()['overview']
    assert ov['progress_rate'] == 0.0


def test_overview_progress_rate_fully_complete(admin_client, project_id):
    _create(admin_client, project_id, effort=5, progress=100)
    _create(admin_client, project_id, effort=3, progress=100)
    ov = admin_client.get(f'/api/wbs/{project_id}/weekly-stats').get_json()['overview']
    assert ov['progress_rate'] == 100.0

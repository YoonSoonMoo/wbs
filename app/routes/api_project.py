from flask import Blueprint, g, jsonify, request

from app.auth import admin_required, api_login_required, project_access_required
from app.extensions import get_db
from app.models import project as project_model
from app.services.auth_service import get_all_users, get_project_members, set_project_members

api_project_bp = Blueprint('api_project', __name__)


@api_project_bp.route('', methods=['GET'])
@api_login_required
def list_projects():
    if g.user['role'] == 'admin':
        projects = [dict(p, my_role='admin') for p in project_model.get_all_projects()]
    else:
        db = get_db()
        rows = db.execute(
            """SELECT p.*, pm.role AS my_role FROM project p
               JOIN project_member pm ON p.id = pm.project_id
               WHERE pm.user_id = ?
               ORDER BY p.created_at DESC""",
            (g.user['id'],),
        ).fetchall()
        projects = [dict(r) for r in rows]
    return jsonify(projects)


@api_project_bp.route('', methods=['POST'])
@api_login_required
@admin_required
def create_project():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '프로젝트명은 필수입니다.'}), 400

    project_id = project_model.create_project(data)

    members = data.get('members', [])
    if members:
        set_project_members(project_id, members)

    project = project_model.get_project(project_id)
    return jsonify(project), 201


@api_project_bp.route('/<int:project_id>', methods=['GET'])
@api_login_required
def get_project(project_id):
    project = project_model.get_project(project_id)
    if not project:
        return jsonify({'error': '프로젝트를 찾을 수 없습니다.'}), 404
    return jsonify(project)


@api_project_bp.route('/<int:project_id>', methods=['PUT'])
@api_login_required
@project_access_required('pm')
def update_project(project_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': '수정할 데이터가 없습니다.'}), 400

    project = project_model.get_project(project_id)
    if not project:
        return jsonify({'error': '프로젝트를 찾을 수 없습니다.'}), 404

    project_model.update_project(project_id, data)

    # 이 라우트는 pm 이상만 도달(project_access_required('pm')) → 멤버/역할 지정 허용
    if 'members' in data:
        set_project_members(project_id, data['members'])

    return jsonify(project_model.get_project(project_id))


@api_project_bp.route('/<int:project_id>', methods=['DELETE'])
@api_login_required
@project_access_required('pm')
def delete_project(project_id):
    project = project_model.get_project(project_id)
    if not project:
        return jsonify({'error': '프로젝트를 찾을 수 없습니다.'}), 404

    project_model.delete_project(project_id)
    return jsonify({'message': '프로젝트가 삭제되었습니다.'})


@api_project_bp.route('/<int:project_id>/history-flag', methods=['PATCH'])
@api_login_required
@project_access_required('pm')
def set_history_flag(project_id):
    """프로젝트의 변경 이력 기록 ON/OFF 토글. (admin/PM)"""
    project = project_model.get_project(project_id)
    if not project:
        return jsonify({'error': '프로젝트를 찾을 수 없습니다.'}), 404
    data = request.get_json() or {}
    enabled = 1 if data.get('enabled') else 0
    project_model.update_project(project_id, {'history_enabled': enabled})
    return jsonify({'id': project_id, 'history_enabled': enabled})


@api_project_bp.route('/scheduler/status', methods=['GET'])
@api_login_required
@admin_required
def scheduler_status():
    """태스크 알림 스케줄러 작동 상태 조회. (admin 진단용)"""
    from app.scheduler import get_status
    return jsonify(get_status())


@api_project_bp.route('/<int:project_id>/members', methods=['GET'])
@api_login_required
def list_project_members(project_id):
    members = get_project_members(project_id)
    return jsonify(members)


@api_project_bp.route('/users', methods=['GET'])
@api_login_required
def list_users():
    users = [u for u in get_all_users() if u['role'] != 'admin']
    return jsonify(users)

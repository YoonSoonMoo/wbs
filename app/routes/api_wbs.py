from flask import Blueprint, g, jsonify, request, session

from app.auth import api_login_required, project_access_required
from app.models import wbs_item as wbs_model
from app.services import dashboard_service, wbs_service
from app.services.auth_service import get_project_role

api_wbs_bp = Blueprint('api_wbs', __name__)


def _check_item_write(item_id):
    """항목 ID로부터 프로젝트 접근 권한을 확인한다. (participant 이상)"""
    item = wbs_model.get_item(item_id)
    if not item:
        return None, jsonify({'error': '항목을 찾을 수 없습니다.'}), 404
    role = get_project_role(session['user_id'], item['project_id'])
    if not role or role == 'viewer':
        return None, jsonify({'error': '권한이 부족합니다.'}), 403
    return item, None, None


# --- WBS 항목 CRUD ---

@api_wbs_bp.route('/<int:project_id>/items', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def list_items(project_id):
    mode = request.args.get('mode', 'flat')
    if mode == 'tree':
        items = wbs_service.get_tree(project_id)
    else:
        items = wbs_service.get_flat_list(project_id)
    return jsonify(items)


@api_wbs_bp.route('/<int:project_id>/items', methods=['POST'])
@api_login_required
@project_access_required('participant')
def create_item(project_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': '데이터가 없습니다.'}), 400
    data['project_id'] = project_id
    item = wbs_service.create_item(data)
    return jsonify(item), 201


@api_wbs_bp.route('/items/<int:item_id>', methods=['GET'])
@api_login_required
def get_item(item_id):
    item = wbs_model.get_item(item_id)
    if not item:
        return jsonify({'error': '항목을 찾을 수 없습니다.'}), 404
    return jsonify(item)


@api_wbs_bp.route('/items/<int:item_id>', methods=['PUT'])
@api_login_required
def update_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    if not data:
        return jsonify({'error': '수정할 데이터가 없습니다.'}), 400
    result = wbs_service.update_item(item_id, data)
    return jsonify(result)


@api_wbs_bp.route('/items/<int:item_id>', methods=['PATCH'])
@api_login_required
def patch_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    if not data:
        return jsonify({'error': '수정할 데이터가 없습니다.'}), 400
    result = wbs_service.update_item(item_id, data)
    return jsonify(result)


@api_wbs_bp.route('/items/<int:item_id>', methods=['DELETE'])
@api_login_required
def delete_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    wbs_service.delete_item(item_id)
    return jsonify({'message': '항목이 삭제되었습니다.'})


# --- 이동/순서변경 ---

@api_wbs_bp.route('/items/<int:item_id>/move', methods=['POST'])
@api_login_required
def move_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    result = wbs_service.move_item(item_id, data.get('parent_id'), data.get('sort_order', 0))
    return jsonify(result)


@api_wbs_bp.route('/<int:project_id>/items/batch', methods=['POST'])
@api_login_required
@project_access_required('participant')
def batch_update(project_id):
    data = request.get_json()
    if not data or not isinstance(data.get('items'), list):
        return jsonify({'error': '항목 목록이 필요합니다.'}), 400
    results = wbs_service.batch_update(project_id, data['items'])
    return jsonify(results)


# --- 통계 ---

@api_wbs_bp.route('/<int:project_id>/stats', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_stats(project_id):
    stats = wbs_service.get_stats(project_id)
    return jsonify(stats)


@api_wbs_bp.route('/<int:project_id>/delayed', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_delayed(project_id):
    items = dashboard_service.get_delayed_items(project_id)
    return jsonify(items)


@api_wbs_bp.route('/<int:project_id>/dashboard', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_dashboard(project_id):
    return jsonify({
        'overview': dashboard_service.get_overview(project_id),
        'by_category': dashboard_service.get_progress_by_category(project_id),
        'by_assignee': dashboard_service.get_assignee_workload(project_id),
        'timeline': dashboard_service.get_timeline_data(project_id),
    })

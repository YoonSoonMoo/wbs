from flask import Blueprint, g, jsonify, request, session

from app.auth import admin_required, api_login_required
from app.services import auth_service

api_users_bp = Blueprint('api_users', __name__)


@api_users_bp.route('', methods=['GET'])
@api_login_required
@admin_required
def list_users():
    users = auth_service.get_all_users()
    return jsonify(users)


@api_users_bp.route('/<int:user_id>/role', methods=['PUT'])
@api_login_required
@admin_required
def update_role(user_id):
    data = request.get_json() or {}
    role = (data.get('role') or '').strip()
    try:
        auth_service.update_user_role(user_id, role)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@api_users_bp.route('/<int:user_id>/reset-password', methods=['POST'])
@api_login_required
@admin_required
def reset_password(user_id):
    data = request.get_json() or {}
    password = data.get('password') or ''
    try:
        auth_service.reset_user_password(user_id, password)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@api_users_bp.route('/<int:user_id>/active', methods=['PUT'])
@api_login_required
@admin_required
def set_active(user_id):
    data = request.get_json() or {}
    is_active = bool(data.get('is_active'))
    # 본인 계정은 비활성화 금지
    if user_id == session.get('user_id') and not is_active:
        return jsonify({'error': '본인 계정은 비활성화할 수 없습니다.'}), 400
    auth_service.set_user_active(user_id, is_active)
    return jsonify({'ok': True})

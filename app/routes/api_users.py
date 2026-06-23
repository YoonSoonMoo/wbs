import random
import string
from flask import Blueprint, g, jsonify, request, session

from app.auth import admin_required, api_login_required
from app.services import auth_service
from app.services.mail_service import send_html_mail

api_users_bp = Blueprint('api_users', __name__)


@api_users_bp.route('/me', methods=['GET'])
@api_login_required
def get_me():
    """현재 인증 주체(세션 또는 API 토큰)의 정보를 반환한다. 외부 클라이언트가 담당자명을 확인하는 용도."""
    return jsonify({
        'id': g.user['id'],
        'name': g.user['name'],
        'email': g.user['email'],
        'role': g.user['role'],
    })


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
    user = auth_service.get_user(user_id)
    if not user:
        return jsonify({'error': '유저를 찾을 수 없습니다.'}), 404
        
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    temp_password = ''.join(random.choice(chars) for _ in range(10))
    
    try:
        auth_service.reset_user_password(user_id, temp_password, require_change=True)
        
        subject = "[Easy WBS] 임시 비밀번호 안내"
        html_body = f"<p>안녕하세요, {user['name']}님.</p><p>임시 비밀번호가 발급되었습니다: <strong>{temp_password}</strong></p><p>로그인 후 즉시 비밀번호를 변경해 주시기 바랍니다.</p>"
        
        send_html_mail(user['email'], user['name'], subject, html_body)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@api_users_bp.route('/<int:user_id>/api-token', methods=['POST'])
@api_login_required
@admin_required
def issue_api_token(user_id):
    """관리자가 특정 유저의 API 토큰을 발급하고 해당 유저 이메일로 전송한다.

    평문 토큰은 응답에 포함하지 않고 이메일로만 전달한다(비밀번호 리셋과 동일 정책).
    """
    user = auth_service.get_user(user_id)
    if not user:
        return jsonify({'error': '유저를 찾을 수 없습니다.'}), 404

    token = auth_service.generate_api_token(user_id)

    subject = "[Easy WBS] API 토큰 발급 안내"
    html_body = (
        f"<p>안녕하세요, {user['name']}님.</p>"
        f"<p>Claude CLI 등 외부 도구에서 WBS에 접근할 수 있는 API 토큰이 발급되었습니다:</p>"
        f"<p><strong>{token}</strong></p>"
        f"<p>이 토큰은 비밀번호와 동일하게 취급해 주세요. 외부에 노출되지 않도록 보관하고, "
        f"코드 저장소에 커밋하지 마세요. 토큰이 유출된 경우 관리자에게 재발급을 요청하시면 "
        f"기존 토큰은 즉시 무효화됩니다.</p>"
    )
    ok, msg = send_html_mail(user['email'], user['name'], subject, html_body)
    if not ok:
        return jsonify({'error': f'메일 발송 실패: {msg}'}), 502
    return jsonify({'ok': True})


@api_users_bp.route('/<int:user_id>/api-token', methods=['DELETE'])
@api_login_required
@admin_required
def revoke_api_token(user_id):
    """관리자가 특정 유저의 API 토큰을 폐기한다."""
    user = auth_service.get_user(user_id)
    if not user:
        return jsonify({'error': '유저를 찾을 수 없습니다.'}), 404
    auth_service.revoke_api_token(user_id)
    return jsonify({'ok': True})


@api_users_bp.route('/me/password', methods=['PUT'])
@api_login_required
def change_my_password():
    data = request.get_json() or {}
    new_password = data.get('password')
    if not new_password or len(new_password) < 4:
         return jsonify({'error': '비밀번호는 4자 이상이어야 합니다.'}), 400
         
    user_id = session.get('user_id')
    try:
        auth_service.reset_user_password(user_id, new_password, require_change=False)
        session.pop('requires_pw_change', None)
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

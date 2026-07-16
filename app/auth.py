from functools import wraps

from flask import g, jsonify, redirect, request, session, url_for

from app.services.auth_service import get_project_role, get_user, get_user_by_api_token


def _bearer_token():
    """Authorization: Bearer <token> 헤더에서 토큰을 추출한다."""
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[len('Bearer '):].strip()
    return None


def _resolve_api_user():
    """API 요청의 인증 주체를 반환한다. Bearer 토큰 우선, 없으면 세션."""
    token = _bearer_token()
    if token:
        return get_user_by_api_token(token)
    user_id = session.get('user_id')
    if user_id:
        return get_user(user_id)
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('auth.login'))
        g.user = get_user(user_id)
        if not g.user:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g.user = _resolve_api_user()
        if not g.user:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        return f(*args, **kwargs)
    return decorated


def project_access_required(min_role='viewer'):
    role_level = {'viewer': 0, 'developer': 1, 'pl': 2, 'pm': 3, 'admin': 4}

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            project_id = kwargs.get('project_id')
            if project_id is None:
                return jsonify({'error': '프로젝트 ID가 필요합니다.'}), 400
            role = get_project_role(g.user['id'], project_id)
            if role is None:
                return jsonify({'error': '이 프로젝트에 접근 권한이 없습니다.'}), 403
            if role_level.get(role, 0) < role_level.get(min_role, 0):
                return jsonify({'error': '권한이 부족합니다.'}), 403
            g.project_role = role
            return f(*args, **kwargs)
        return decorated
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.user['role'] != 'admin':
            return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated

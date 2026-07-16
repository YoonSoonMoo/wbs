import hashlib
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import get_db


def _hash_api_token(token):
    """API 토큰을 SHA-256 16진 해시로 변환한다 (고엔트로피 토큰이라 솔트 불필요)."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def register_user(name, email, password, role='viewer'):
    db = get_db()
    pw_hash = generate_password_hash(password)
    try:
        cursor = db.execute(
            "INSERT INTO user (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, pw_hash, role),
        )
        db.commit()
        return cursor.lastrowid
    except Exception:
        raise ValueError("이미 등록된 이메일입니다.")


def login_user(email, password):
    db = get_db()
    user = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
    if not user or not check_password_hash(user['password_hash'], password):
        return None
    if not user['is_active']:
        return {'_inactive': True}
    return dict(user)


def get_user(user_id):
    db = get_db()
    row = db.execute(
        "SELECT id, name, email, role, is_active FROM user WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def get_all_users():
    db = get_db()
    rows = db.execute(
        "SELECT id, name, email, role, is_active, created_at FROM user ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


# 전역 역할(user.role): 관리자(admin) / 일반 사용자(developer) 2단계.
# 업무 권한(pm/pl/developer/viewer)은 프로젝트별(project_member.role)로만 지정한다.
VALID_ROLES = ('admin', 'developer')
# 프로젝트별 역할(project_member.role): 권한 판정의 실제 출처
PROJECT_MEMBER_ROLES = ('pm', 'pl', 'developer', 'viewer')


def update_user_role(user_id, new_role):
    if new_role not in VALID_ROLES:
        raise ValueError(f"잘못된 역할: {new_role}")
    db = get_db()
    db.execute("UPDATE user SET role = ? WHERE id = ?", (new_role, user_id))
    # 전역 admin 승격 시 프로젝트 멤버 행 제거(모든 프로젝트에서 admin으로 동작).
    # 그 외 전역 역할 변경은 프로젝트별 역할(project_member.role)을 건드리지 않는다.
    if new_role == 'admin':
        db.execute("DELETE FROM project_member WHERE user_id = ?", (user_id,))
    db.commit()


def reset_user_password(user_id, new_password, require_change=False):
    if not new_password or len(new_password) < 4:
        raise ValueError("비밀번호는 4자 이상이어야 합니다.")
    db = get_db()
    db.execute(
        "UPDATE user SET password_hash = ?, requires_password_change = ? WHERE id = ?",
        (generate_password_hash(new_password), 1 if require_change else 0, user_id),
    )
    db.commit()


def set_user_active(user_id, is_active):
    db = get_db()
    db.execute("UPDATE user SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
    db.commit()


def generate_api_token(user_id):
    """유저의 API 토큰을 새로 발급한다. 평문 토큰을 1회 반환하며, DB에는 해시만 저장한다."""
    token = secrets.token_urlsafe(32)
    db = get_db()
    db.execute(
        "UPDATE user SET api_token_hash = ? WHERE id = ?",
        (_hash_api_token(token), user_id),
    )
    db.commit()
    return token


def revoke_api_token(user_id):
    """유저의 API 토큰을 폐기한다."""
    db = get_db()
    db.execute("UPDATE user SET api_token_hash = NULL WHERE id = ?", (user_id,))
    db.commit()


def get_user_by_api_token(token):
    """API 토큰으로 활성 유저를 조회한다. 토큰이 없거나 비활성 계정이면 None."""
    if not token:
        return None
    db = get_db()
    row = db.execute(
        "SELECT id, name, email, role, is_active FROM user "
        "WHERE api_token_hash = ? AND is_active = 1",
        (_hash_api_token(token),),
    ).fetchone()
    return dict(row) if row else None


_ROLE_LEVEL = {'viewer': 0, 'developer': 1, 'admin': 2}


def get_project_role(user_id, project_id):
    """프로젝트 내 유효 권한을 반환한다.

    전역 admin이면 항상 'admin'. 그 외에는 해당 프로젝트의 project_member.role
    (pm/pl/developer/viewer)을 반환한다. 멤버가 아니면 None.
    """
    user = get_user(user_id)
    if not user:
        return None
    if user['role'] == 'admin':
        return 'admin'
    db = get_db()
    row = db.execute(
        "SELECT role FROM project_member WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    if not row:
        return None
    return row['role']


def get_project_members(project_id):
    db = get_db()
    rows = db.execute(
        """SELECT u.id, u.name, u.email, pm.role
           FROM project_member pm
           JOIN user u ON pm.user_id = u.id
           WHERE pm.project_id = ?
           ORDER BY u.name""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_project_members(project_id, members):
    """프로젝트 멤버와 프로젝트별 역할을 갱신한다. (admin 전용 경로에서만 호출)

    member의 role(pm/pl/developer/viewer)은 멤버 지정 UI(admin 전용)가 보낸 값을 저장한다.
    전역 admin 유저는 모든 프로젝트에서 admin이므로 멤버로 등록하지 않는다.
    """
    db = get_db()
    db.execute("DELETE FROM project_member WHERE project_id = ?", (project_id,))
    seen = set()
    for m in members:
        uid = m['user_id']
        if uid in seen:
            continue
        seen.add(uid)
        u = db.execute("SELECT role FROM user WHERE id = ?", (uid,)).fetchone()
        if not u or u['role'] == 'admin':
            continue
        role = m.get('role')
        if role not in PROJECT_MEMBER_ROLES:
            role = 'developer'  # 미지정/유효하지 않은 값은 기본 개발자
        db.execute(
            "INSERT INTO project_member (project_id, user_id, role) VALUES (?, ?, ?)",
            (project_id, uid, role),
        )
    db.commit()


def ensure_admin_exists():
    from flask import current_app
    db = get_db()
    count = db.execute("SELECT COUNT(*) as cnt FROM user").fetchone()['cnt']
    if count == 0:
        name = current_app.config.get('ADMIN_NAME', '관리자')
        email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
        password = current_app.config.get('ADMIN_PASSWORD', 'admin1234')
        register_user(name, email, password, role='admin')

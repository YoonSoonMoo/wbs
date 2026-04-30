from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import get_db


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


VALID_ROLES = ('admin', 'developer', 'viewer')


def update_user_role(user_id, new_role):
    if new_role not in VALID_ROLES:
        raise ValueError(f"잘못된 역할: {new_role}")
    db = get_db()
    db.execute("UPDATE user SET role = ? WHERE id = ?", (new_role, user_id))
    if new_role == 'admin':
        # 전역 admin은 모든 프로젝트에서 admin으로 동작 → 멤버 테이블에서 제거
        db.execute("DELETE FROM project_member WHERE user_id = ?", (user_id,))
    else:
        # 일반 권한 변경 시 project_member.role 동기화 (불일치 방지)
        db.execute("UPDATE project_member SET role = ? WHERE user_id = ?", (new_role, user_id))
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


_ROLE_LEVEL = {'viewer': 0, 'developer': 1, 'admin': 2}


def get_project_role(user_id, project_id):
    """프로젝트 내 유효 권한을 반환한다.

    권한은 유저 관리(user.role)에서 단일 관리한다. project_member 테이블은
    "이 프로젝트에 어떤 유저가 속해 있는가"만 표현하고, role은 user.role을 그대로 사용한다.
    """
    user = get_user(user_id)
    if not user:
        return None
    if user['role'] == 'admin':
        return 'admin'
    db = get_db()
    row = db.execute(
        "SELECT 1 FROM project_member WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    if not row:
        return None
    return user['role']


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
    """프로젝트 멤버를 갱신한다.

    member의 role은 받지 않으며(권한은 user.role에서 통합 관리), DB의 project_member.role은
    user.role을 그대로 복제해 둔다(스키마 NOT NULL 제약 충족 + 데이터 일관성 유지).
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
        db.execute(
            "INSERT INTO project_member (project_id, user_id, role) VALUES (?, ?, ?)",
            (project_id, uid, u['role']),
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

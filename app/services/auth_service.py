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
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None


def get_user(user_id):
    db = get_db()
    row = db.execute(
        "SELECT id, name, email, role FROM user WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(row) if row else None


def get_all_users():
    db = get_db()
    rows = db.execute("SELECT id, name, email, role FROM user ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_project_role(user_id, project_id):
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
    return row['role'] if row else None


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
    db = get_db()
    db.execute("DELETE FROM project_member WHERE project_id = ?", (project_id,))
    for m in members:
        db.execute(
            "INSERT INTO project_member (project_id, user_id, role) VALUES (?, ?, ?)",
            (project_id, m['user_id'], m['role']),
        )
    db.commit()


def ensure_admin_exists():
    db = get_db()
    count = db.execute("SELECT COUNT(*) as cnt FROM user").fetchone()['cnt']
    if count == 0:
        register_user('윤순무', 'yoonsm@daou.co.kr', 'zaq12wsx', role='admin')

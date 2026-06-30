from app.extensions import get_db


def get_all_projects():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM project ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_project(project_id):
    db = get_db()
    row = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def create_project(data):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO project (name, description, start_date, end_date, notice, "
        "task_notify_enabled, task_notify_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (data['name'], data.get('description', ''), data.get('start_date'), data.get('end_date'),
         data.get('notice', ''), 1 if data.get('task_notify_enabled') else 0,
         data.get('task_notify_time', '09:00')),
    )
    db.commit()
    return cursor.lastrowid


def update_project(project_id, data):
    db = get_db()
    fields = []
    values = []
    for key in ('name', 'description', 'start_date', 'end_date', 'history_enabled', 'notice',
                'task_notify_enabled', 'task_notify_time'):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return False
    values.append(project_id)
    db.execute(f"UPDATE project SET {', '.join(fields)} WHERE id = ?", values)
    db.commit()
    return True


def delete_project(project_id):
    db = get_db()
    db.execute("DELETE FROM project WHERE id = ?", (project_id,))
    db.commit()
    return True

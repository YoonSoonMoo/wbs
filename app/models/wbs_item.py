from app.extensions import get_db

EDITABLE_FIELDS = (
    'parent_id', 'wbs_code', 'level', 'sort_order',
    'category', 'task_name', 'subtask', 'detail', 'description',
    'plan_start', 'plan_end', 'actual_start', 'actual_end',
    'assignee', 'effort', 'progress', 'status',
    'priority', 'is_milestone',
)


def get_items_by_project(project_id):
    db = get_db()
    rows = db.execute(
        """WITH RECURSIVE tree AS (
            SELECT *, 0 as depth FROM wbs_item
            WHERE project_id = ? AND parent_id IS NULL
            UNION ALL
            SELECT c.*, t.depth + 1 FROM wbs_item c
            JOIN tree t ON c.parent_id = t.id
        )
        SELECT * FROM tree ORDER BY wbs_code""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_flat_items(project_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM wbs_item WHERE project_id = ? ORDER BY sort_order",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM wbs_item WHERE id = ?", (item_id,)).fetchone()
    return dict(row) if row else None


def _trim(value):
    """문자열이면 앞뒤 공백을 제거한다."""
    return value.strip() if isinstance(value, str) else value


def create_item(data):
    db = get_db()
    cursor = db.execute(
        """INSERT INTO wbs_item
           (project_id, parent_id, wbs_code, level, sort_order,
            category, task_name, subtask, detail, description,
            plan_start, plan_end, actual_start, actual_end,
            assignee, effort, progress, status, priority, is_milestone)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['project_id'],
            data.get('parent_id'),
            _trim(data.get('wbs_code', '')),
            data.get('level', 0),
            data.get('sort_order', 0),
            _trim(data.get('category', '')),
            _trim(data.get('task_name', '')),
            _trim(data.get('subtask', '')),
            _trim(data.get('detail', '')),
            _trim(data.get('description', '')),
            _trim(data.get('plan_start')),
            _trim(data.get('plan_end')),
            _trim(data.get('actual_start')),
            _trim(data.get('actual_end')),
            _trim(data.get('assignee', '')),
            data.get('effort', 0),
            data.get('progress', 0),
            _trim(data.get('status', '대기')),
            _trim(data.get('priority', 'medium')),
            data.get('is_milestone', 0),
        ),
    )
    db.commit()
    return cursor.lastrowid


def update_item(item_id, data):
    db = get_db()
    fields = []
    values = []
    for key in EDITABLE_FIELDS:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(_trim(data[key]))
    if not fields:
        return False
    values.append(item_id)
    db.execute(f"UPDATE wbs_item SET {', '.join(fields)} WHERE id = ?", values)
    db.commit()
    return True


def delete_item(item_id):
    db = get_db()
    db.execute("UPDATE wbs_item SET parent_id = NULL WHERE parent_id = ?", (item_id,))
    db.execute("DELETE FROM wbs_item WHERE id = ?", (item_id,))
    db.commit()
    return True


def get_children(parent_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM wbs_item WHERE parent_id = ? ORDER BY sort_order",
        (parent_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_max_sort_order(project_id, parent_id=None):
    db = get_db()
    if parent_id is None:
        row = db.execute(
            "SELECT MAX(sort_order) as max_order FROM wbs_item WHERE project_id = ? AND parent_id IS NULL",
            (project_id,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT MAX(sort_order) as max_order FROM wbs_item WHERE project_id = ? AND parent_id = ?",
            (project_id, parent_id),
        ).fetchone()
    return (row['max_order'] or 0) if row else 0

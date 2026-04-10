from app.extensions import get_db


def recalculate_codes(project_id, parent_id=None, prefix=""):
    """특정 부모 아래 모든 자식의 WBS 코드를 재귀적으로 재계산한다."""
    db = get_db()
    if parent_id is None:
        children = db.execute(
            "SELECT id FROM wbs_item WHERE project_id = ? AND parent_id IS NULL ORDER BY sort_order",
            (project_id,),
        ).fetchall()
    else:
        children = db.execute(
            "SELECT id FROM wbs_item WHERE project_id = ? AND parent_id = ? ORDER BY sort_order",
            (project_id, parent_id),
        ).fetchall()

    for idx, child in enumerate(children, 1):
        if parent_id is None:
            code = f"{idx}.0"
            child_prefix = str(idx)
        else:
            code = f"{prefix}.{idx}"
            child_prefix = code

        level = code.count('.') if parent_id is not None else 0
        db.execute(
            "UPDATE wbs_item SET wbs_code = ?, level = ? WHERE id = ?",
            (code, level, child['id']),
        )
        recalculate_codes(project_id, child['id'], child_prefix)

    db.commit()


def get_next_sort_order(project_id, parent_id=None):
    """동일 부모 아래 다음 sort_order 값을 반환한다."""
    db = get_db()
    if parent_id is None:
        row = db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 as next_order "
            "FROM wbs_item WHERE project_id = ? AND parent_id IS NULL",
            (project_id,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 as next_order "
            "FROM wbs_item WHERE project_id = ? AND parent_id = ?",
            (project_id, parent_id),
        ).fetchone()
    return row['next_order']

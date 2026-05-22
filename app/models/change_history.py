from app.extensions import get_db

TRACKED_FIELDS = ('detail', 'assignee', 'plan_start', 'plan_end', 'effort', 'progress')

FIELD_LABELS = {
    'detail': '세부항목',
    'assignee': '담당자',
    'plan_start': '계획시작',
    'plan_end': '계획완료',
    'effort': '공수',
    'progress': '진행률',
}


def _norm(v):
    if v is None:
        return ''
    return str(v).strip()


def _eq(a, b, field):
    """추적 필드에 맞춘 동등 비교. effort/progress는 숫자 비교."""
    if field in ('effort', 'progress'):
        try:
            af = float(a) if a not in (None, '') else 0.0
            bf = float(b) if b not in (None, '') else 0.0
            return af == bf
        except (TypeError, ValueError):
            return _norm(a) == _norm(b)
    return _norm(a) == _norm(b)


def record_changes(project_id, item_id, before, after, changed_by, snapshot_detail='', snapshot_assignee=''):
    """before/after 데이터를 비교하여 추적 필드의 변경만 wbs_change_history에 기록한다.

    before/after는 dict (wbs_item row). after에는 변경 요청 필드만 들어있을 수 있으므로
    after에 없는 키는 비교하지 않는다.
    """
    db = get_db()
    rows = []
    for field in TRACKED_FIELDS:
        if field not in after:
            continue
        old_v = before.get(field) if before else None
        new_v = after.get(field)
        if _eq(old_v, new_v, field):
            continue
        rows.append((project_id, item_id, changed_by or '', field, _norm(old_v), _norm(new_v),
                     snapshot_detail or '', snapshot_assignee or ''))
    if not rows:
        return 0
    db.executemany(
        """INSERT INTO wbs_change_history
           (project_id, item_id, changed_by, field, old_value, new_value, snapshot_detail, snapshot_assignee)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    db.commit()
    return len(rows)


def list_changes(project_id, limit=200, offset=0):
    db = get_db()
    rows = db.execute(
        """SELECT id, item_id, changed_at, changed_by, field, old_value, new_value,
                  snapshot_detail, snapshot_assignee
             FROM wbs_change_history
            WHERE project_id = ?
            ORDER BY changed_at DESC, id DESC
            LIMIT ? OFFSET ?""",
        (project_id, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def count_changes(project_id):
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM wbs_change_history WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    return row['cnt'] if row else 0

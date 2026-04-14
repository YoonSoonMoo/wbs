from app.extensions import get_db
from app.models import wbs_item as wbs_model
from app.services.wbs_code_service import get_next_sort_order, recalculate_codes


def get_tree(project_id):
    """프로젝트의 WBS 항목을 중첩 트리 구조로 반환한다."""
    items = wbs_model.get_items_by_project(project_id)
    return _build_tree(items)


def get_flat_list(project_id):
    """프로젝트의 WBS 항목을 평탄한 리스트로 반환한다 (그리드 뷰용)."""
    return wbs_model.get_flat_items(project_id)


def create_item(data):
    """WBS 항목을 생성하고 WBS 코드를 재계산한다."""
    project_id = data['project_id']
    parent_id = data.get('parent_id')

    data['sort_order'] = get_next_sort_order(project_id, parent_id)
    item_id = wbs_model.create_item(data)
    recalculate_codes(project_id)
    return wbs_model.get_item(item_id)


def update_item(item_id, data):
    """WBS 항목을 수정한다. parent_id 변경 시 WBS 코드를 재계산한다."""
    item = wbs_model.get_item(item_id)
    if not item:
        return None

    parent_changed = 'parent_id' in data and data['parent_id'] != item['parent_id']

    if parent_changed:
        data['sort_order'] = get_next_sort_order(item['project_id'], data['parent_id'])

    wbs_model.update_item(item_id, data)

    if parent_changed:
        recalculate_codes(item['project_id'])

    return wbs_model.get_item(item_id)


def delete_item(item_id):
    """WBS 항목과 모든 자식을 삭제하고 WBS 코드를 재계산한다."""
    item = wbs_model.get_item(item_id)
    if not item:
        return False

    project_id = item['project_id']
    _delete_recursive(item_id)
    recalculate_codes(project_id)
    return True


def move_item(item_id, new_parent_id, new_sort_order):
    """항목을 새 위치로 이동한다."""
    item = wbs_model.get_item(item_id)
    if not item:
        return None

    project_id = item['project_id']
    db = get_db()

    # 같은 부모 내 이동: sort_order 조정
    if new_parent_id == item['parent_id']:
        _reorder_siblings(project_id, new_parent_id, item_id, new_sort_order)
    else:
        # 다른 부모로 이동
        wbs_model.update_item(item_id, {
            'parent_id': new_parent_id,
            'sort_order': new_sort_order,
        })

    recalculate_codes(project_id)
    return wbs_model.get_item(item_id)


def batch_update(project_id, items_data):
    """여러 항목을 일괄 수정한다."""
    results = []
    for item_data in items_data:
        item_id = item_data.pop('id', None)
        if item_id:
            wbs_model.update_item(item_id, item_data)
            results.append(wbs_model.get_item(item_id))
    recalculate_codes(project_id)
    return results


def get_stats(project_id):
    """프로젝트의 WBS 통계를 반환한다."""
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) as cnt FROM wbs_item WHERE project_id = ?", (project_id,)
    ).fetchone()['cnt']

    completed = db.execute(
        "SELECT COUNT(*) as cnt FROM wbs_item WHERE project_id = ? AND progress = 100",
        (project_id,),
    ).fetchone()['cnt']

    in_progress = db.execute(
        "SELECT COUNT(*) as cnt FROM wbs_item WHERE project_id = ? AND progress > 0 AND progress < 100",
        (project_id,),
    ).fetchone()['cnt']

    not_started = db.execute(
        "SELECT COUNT(*) as cnt FROM wbs_item WHERE project_id = ? AND progress = 0",
        (project_id,),
    ).fetchone()['cnt']

    delayed = db.execute(
        """SELECT COUNT(*) as cnt FROM wbs_item
           WHERE project_id = ? AND plan_end IS NOT NULL AND plan_end < date('now','localtime')
           AND progress < 100""",
        (project_id,),
    ).fetchone()['cnt']

    avg_progress = db.execute(
        "SELECT COALESCE(AVG(progress), 0) as avg FROM wbs_item WHERE project_id = ?",
        (project_id,),
    ).fetchone()['avg']

    return {
        'total': total,
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started,
        'delayed': delayed,
        'avg_progress': round(avg_progress, 1),
    }


def _build_tree(items):
    """평탄한 리스트를 중첩 트리 구조로 변환한다."""
    item_map = {}
    roots = []
    for item in items:
        item['children'] = []
        item_map[item['id']] = item

    for item in items:
        parent_id = item.get('parent_id')
        if parent_id and parent_id in item_map:
            item_map[parent_id]['children'].append(item)
        else:
            roots.append(item)

    return roots


def _delete_recursive(item_id):
    """항목과 모든 자식을 재귀적으로 삭제한다."""
    db = get_db()
    children = db.execute(
        "SELECT id FROM wbs_item WHERE parent_id = ?", (item_id,)
    ).fetchall()
    for child in children:
        _delete_recursive(child['id'])
    db.execute("DELETE FROM wbs_item WHERE id = ?", (item_id,))
    db.commit()


def _reorder_siblings(project_id, parent_id, moved_id, new_order):
    """동일 부모 내 형제 노드의 순서를 조정한다."""
    db = get_db()
    if parent_id is None:
        siblings = db.execute(
            "SELECT id FROM wbs_item WHERE project_id = ? AND parent_id IS NULL AND id != ? ORDER BY sort_order",
            (project_id, moved_id),
        ).fetchall()
    else:
        siblings = db.execute(
            "SELECT id FROM wbs_item WHERE project_id = ? AND parent_id = ? AND id != ? ORDER BY sort_order",
            (project_id, parent_id, moved_id),
        ).fetchall()

    sibling_ids = [s['id'] for s in siblings]
    sibling_ids.insert(new_order, moved_id)

    for idx, sid in enumerate(sibling_ids):
        db.execute("UPDATE wbs_item SET sort_order = ? WHERE id = ?", (idx, sid))
    db.commit()

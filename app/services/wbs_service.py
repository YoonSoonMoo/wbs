from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import get_db
from app.models import wbs_item as wbs_model
from app.services.wbs_code_service import get_next_sort_order, recalculate_codes


def _round_half_up_1(value) -> float:
    """소수 둘째자리에서 사사오입하여 소수 첫째자리까지 반환한다.

    Python 내장 round()는 뱅커즈 라운딩(Half to Even)이라 0.15 → 0.1 이 되는 등
    한국식 '사사오입' 규칙과 맞지 않는다. Decimal + ROUND_HALF_UP 으로 안전하게 처리.
    """
    if value is None:
        return 0.0
    try:
        return float(Decimal(str(value)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
    except (ValueError, ArithmeticError):
        return 0.0


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


def update_item(item_id, data, updated_by=None):
    """WBS 항목을 수정한다. parent_id 변경 시 WBS 코드를 재계산한다."""
    item = wbs_model.get_item(item_id)
    if not item:
        return None

    parent_changed = 'parent_id' in data and data['parent_id'] != item['parent_id']

    if parent_changed:
        data['sort_order'] = get_next_sort_order(item['project_id'], data['parent_id'])

    wbs_model.update_item(item_id, data, updated_by=updated_by)

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


def batch_update(project_id, items_data, updated_by=None):
    """여러 항목을 일괄 수정한다."""
    results = []
    for item_data in items_data:
        item_id = item_data.pop('id', None)
        if item_id:
            wbs_model.update_item(item_id, item_data, updated_by=updated_by)
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


def get_weekly_stats(project_id, num_weeks=8):
    """주차별(월~일) WBS 진척 통계를 반환한다.

    이번 주(진행중) + 이전 num_weeks개 완료 주를 포함한다.
    각 주에 대해 다음을 계산한다:
    - 해당 주 말 기준 누적 전체 태스크 수 / 공수
    - 해당 주에 신규 등록된 태스크 수 / 공수
    - 해당 주에 완료(progress=100)된 태스크 수 / 공수
    - 해당 주 말 기준 전체 진척률 (누적완료/누적전체)
    - 전주 대비 delta
    """
    db = get_db()
    today = date.today()
    monday_of_current = today - timedelta(days=today.weekday())

    def _week_label(mon: date) -> str:
        fri = mon + timedelta(days=4)
        week_num = (fri.day - 1) // 7 + 1
        return f"{fri.month}월 {week_num}주차"

    def _date_range(mon: date, end: date) -> str:
        return f"{mon.month}/{mon.day}~{end.month}/{end.day}"

    # 주차 목록 구성: [이번 주(진행중), 지난 num_weeks개 완료 주] - 최신 순
    weeks = []

    sunday_of_current = monday_of_current + timedelta(days=6)
    friday_of_current = monday_of_current + timedelta(days=4)

    # 0: 이번 주 (진행중, 월요일~일요일)
    weeks.append({
        'week_start': monday_of_current.isoformat(),
        'week_end': sunday_of_current.isoformat(),
        'week_cutoff': today.isoformat(),    # 누적 집계 기준일
        'label': _week_label(monday_of_current) + ' (진행중)',
        'date_range': _date_range(monday_of_current, friday_of_current),
        'is_current': True,
    })

    # 1 ~ num_weeks: 이전 완료 주 (최신 순)
    for i in range(1, num_weeks + 1):
        w_mon = monday_of_current - timedelta(weeks=i)
        w_fri = w_mon + timedelta(days=4)
        w_sun = w_mon + timedelta(days=6)
        weeks.append({
            'week_start': w_mon.isoformat(),
            'week_end': w_sun.isoformat(),
            'week_cutoff': w_fri.isoformat(),  # 금요일 기준 누적 집계
            'label': _week_label(w_mon),
            'date_range': _date_range(w_mon, w_fri),
            'is_current': False,
        })

    def _query_week(ws: str, we: str, cutoff: str):
        """주어진 기간의 통계를 조회한다."""
        row_total = db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(effort), 0) as eff "
            "FROM wbs_item WHERE project_id = ? AND date(created_at) <= ?",
            (project_id, cutoff),
        ).fetchone()

        row_new = db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(effort), 0) as eff "
            "FROM wbs_item WHERE project_id = ? AND date(created_at) BETWEEN ? AND ?",
            (project_id, ws, we),
        ).fetchone()

        # 계획완료(해당 주에 끝내기로 한 태스크): plan_end가 주 범위 안
        row_planned_week = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(effort), 0) as eff
               FROM wbs_item
               WHERE project_id = ?
                 AND plan_end IS NOT NULL AND plan_end != ''
                 AND date(plan_end) BETWEEN ? AND ?""",
            (project_id, ws, we),
        ).fetchone()

        # 주간완료: plan_end와 actual_end가 모두 주 범위 안
        row_completed_week = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(effort), 0) as eff
               FROM wbs_item
               WHERE project_id = ?
                 AND plan_end   IS NOT NULL AND plan_end   != ''
                 AND actual_end IS NOT NULL AND actual_end != ''
                 AND date(plan_end)   BETWEEN ? AND ?
                 AND date(actual_end) BETWEEN ? AND ?""",
            (project_id, ws, we, ws, we),
        ).fetchone()

        row_total_completed = db.execute(
            """SELECT COUNT(*) as cnt, COALESCE(SUM(effort), 0) as eff
               FROM wbs_item
               WHERE project_id = ? AND progress = 100
               AND date(COALESCE(completed_at, updated_at)) <= ?""",
            (project_id, cutoff),
        ).fetchone()

        total_tasks = row_total['cnt']
        total_effort = round(float(row_total['eff']), 1)
        new_tasks = row_new['cnt']
        new_effort = round(float(row_new['eff']), 1)
        planned_week = row_planned_week['cnt']
        planned_week_effort = round(float(row_planned_week['eff']), 1)
        completed_week = row_completed_week['cnt']
        completed_week_effort = round(float(row_completed_week['eff']), 1)
        total_completed = row_total_completed['cnt']
        total_completed_effort = round(float(row_total_completed['eff']), 1)
        progress_rate = round(completed_week / planned_week * 100, 1) if planned_week > 0 else 0.0
        return {
            'total_tasks': total_tasks,
            'total_effort': total_effort,
            'new_tasks': new_tasks,
            'new_effort': new_effort,
            'planned_week': planned_week,
            'planned_week_effort': planned_week_effort,
            'completed_week': completed_week,
            'completed_week_effort': completed_week_effort,
            'total_completed': total_completed,
            'total_completed_effort': total_completed_effort,
            'progress_rate': progress_rate,
        }

    result = []
    for w in weeks:
        stats = _query_week(w['week_start'], w['week_end'], w['week_cutoff'])
        result.append({
            'week_label': w['label'],
            'date_range': w['date_range'],
            'week_start': w['week_start'],
            'week_end': w['week_end'],
            'is_current': w['is_current'],
            **stats,
        })

    # 누적완료 = 관측 구간 내 주간완료(completed_week)의 오래된 주부터의 러닝 합
    # result[0]=최신, result[-1]=가장 오래된
    cum_cnt = 0
    cum_eff = 0.0
    for w in reversed(result):
        cum_cnt += w['completed_week']
        cum_eff += w['completed_week_effort']
        w['cumulative_completed_week'] = cum_cnt
        w['cumulative_completed_week_effort'] = round(cum_eff, 1)

    # 전주 대비 delta 계산 (result[0]=최신, result[-1]=가장 오래된)
    for i in range(len(result)):
        curr = result[i]
        if i + 1 < len(result):
            prev = result[i + 1]
            curr['delta_total'] = curr['total_tasks'] - prev['total_tasks']
            curr['delta_completed_week'] = curr['completed_week'] - prev['completed_week']
            curr['delta_planned_week'] = curr['planned_week'] - prev['planned_week']
            curr['delta_rate'] = round(curr['progress_rate'] - prev['progress_rate'], 1)
            curr['delta_total_effort'] = round(curr['total_effort'] - prev['total_effort'], 1)
            curr['delta_completed_week_effort'] = round(
                curr['completed_week_effort'] - prev['completed_week_effort'], 1
            )
        else:
            curr['delta_total'] = None
            curr['delta_completed_week'] = None
            curr['delta_planned_week'] = None
            curr['delta_rate'] = None
            curr['delta_total_effort'] = None
            curr['delta_completed_week_effort'] = None

    # 현재(라이브) 개요 - 이번 주 통계(result[0])와 동일하지만 오늘 기준 최신값
    row_now = db.execute(
        """SELECT COUNT(*) as total,
               SUM(CASE WHEN progress = 100 THEN 1 ELSE 0 END) as completed,
               COALESCE(SUM(effort), 0) as total_effort,
               COALESCE(SUM(CASE WHEN progress = 100 THEN effort ELSE 0 END), 0) as completed_effort
           FROM wbs_item WHERE project_id = ?""",
        (project_id,),
    ).fetchone()

    total_now = row_now['total'] or 0
    completed_now = row_now['completed'] or 0
    total_effort_now = round(float(row_now['total_effort']), 1)
    completed_effort_now = round(float(row_now['completed_effort']), 1)
    # 전체 진척률 = 완료 공수 / 전체 공수 (공수 기준, 소수 둘째자리 사사오입)
    rate_now = (
        _round_half_up_1(completed_effort_now / total_effort_now * 100)
        if total_effort_now > 0 else 0.0
    )

    # overview delta = 현재 vs 지난 완료 주(result[1])
    overview = {
        'total': total_now,
        'completed': completed_now,
        'total_effort': total_effort_now,
        'completed_effort': completed_effort_now,
        'progress_rate': rate_now,
        'report_week': None,
        'report_date_range': None,
        'delta_total': None,
        'delta_completed': None,
        'delta_rate': None,
        'delta_total_effort': None,
        'delta_completed_effort': None,
    }

    # 전주(가장 최근 완료 주) = result[1]
    if len(result) > 1:
        lw = result[1]
        overview['report_week'] = lw['week_label']
        overview['report_date_range'] = lw['date_range']
        overview['delta_total'] = total_now - lw['total_tasks']
        overview['delta_completed'] = completed_now - lw['total_completed']
        overview['delta_total_effort'] = round(total_effort_now - lw['total_effort'], 1)
        overview['delta_completed_effort'] = round(completed_effort_now - lw['total_completed_effort'], 1)
        overview['delta_rate'] = _round_half_up_1(rate_now - lw['progress_rate'])

    # 담당자별 현황
    rows_assignee = db.execute(
        """SELECT assignee, COUNT(*) as tasks,
               COALESCE(SUM(effort), 0) as effort,
               SUM(CASE WHEN progress = 100 THEN 1 ELSE 0 END) as completed,
               COALESCE(SUM(CASE WHEN progress = 100 THEN effort ELSE 0 END), 0) as completed_effort
           FROM wbs_item WHERE project_id = ? AND assignee != ''
           GROUP BY assignee ORDER BY tasks DESC LIMIT 12""",
        (project_id,),
    ).fetchall()

    return {
        'overview': overview,
        'weekly': result,
        'assignees': [dict(r) for r in rows_assignee],
    }


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

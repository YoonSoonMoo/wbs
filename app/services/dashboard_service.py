from app.extensions import get_db


def get_overview(project_id):
    """대시보드용 프로젝트 개요 통계를 반환한다."""
    from app.services.wbs_service import get_stats
    return get_stats(project_id)


def get_progress_by_category(project_id):
    """카테고리별 진행률을 반환한다."""
    db = get_db()
    rows = db.execute(
        """SELECT category, COUNT(*) as count,
                  ROUND(AVG(progress), 1) as avg_progress
           FROM wbs_item
           WHERE project_id = ? AND category != ''
           GROUP BY category
           ORDER BY category""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_assignee_workload(project_id):
    """담당자별 업무량과 진행률을 반환한다."""
    db = get_db()
    rows = db.execute(
        """SELECT assignee, COUNT(*) as count,
                  SUM(effort) as total_effort,
                  ROUND(AVG(progress), 1) as avg_progress,
                  SUM(CASE WHEN progress = 100 THEN 1 ELSE 0 END) as completed
           FROM wbs_item
           WHERE project_id = ? AND assignee != ''
           GROUP BY assignee
           ORDER BY count DESC""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_delayed_items(project_id):
    """지연 업무 목록을 반환한다."""
    db = get_db()
    rows = db.execute(
        """SELECT * FROM wbs_item
           WHERE project_id = ? AND plan_end IS NOT NULL
           AND plan_end < date('now','localtime') AND progress < 100
           ORDER BY plan_end""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_timeline_data(project_id):
    """Gantt 차트용 타임라인 데이터를 반환한다. 정렬은 그리드와 동일하게 sort_order 기준."""
    db = get_db()
    rows = db.execute(
        """SELECT id, wbs_code, task_name, subtask, detail, parent_id, level,
                  sort_order, plan_start, plan_end, actual_start, actual_end,
                  progress, assignee, is_milestone
           FROM wbs_item
           WHERE project_id = ? AND (plan_start IS NOT NULL OR actual_start IS NOT NULL)
           ORDER BY sort_order""",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]

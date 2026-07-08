"""태스크 갱신 알림 — 이번주 할당 태스크를 담당자별로 메일 발송.

스케줄러(app/scheduler.py)가 프로젝트별 발송시각에 맞춰 호출한다.
"""
import logging
from datetime import date, datetime, timedelta

from flask import current_app

from app.extensions import get_db
from app.models import wbs_item as wbs_model
from app.models.project import get_project
from app.services.mail_service import build_task_update_mail_html, send_html_mail

logger = logging.getLogger(__name__)


def _parse_date(value):
    """'YYYY-MM-DD' 문자열을 date로 파싱한다. 실패 시 None."""
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _this_week_window(today=None):
    """이번주 월요일~일요일 (date, date)."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday())  # 월요일
    return start, start + timedelta(days=6)           # 일요일


def get_week_tasks(project_id):
    """이번주(월~일) 계획기간과 겹치는 미완료 태스크를 반환한다.

    겹침 판정: plan_start <= 주말 AND plan_end >= 주초 (한쪽만 있으면 그 값으로 양끝 대체).
    완료(progress>=100) 항목은 제외.
    """
    items = wbs_model.get_flat_items(project_id)
    week_start, week_end = _this_week_window()
    result = []
    for it in items:
        if (it.get('progress') or 0) >= 100:
            continue
        ps = _parse_date(it.get('plan_start'))
        pe = _parse_date(it.get('plan_end'))
        s = ps or pe
        e = pe or ps
        if s and e and s <= week_end and e >= week_start:
            result.append(it)
    return result


def send_task_update_mails(project_id, base_url=None):
    """이번주 할당 태스크를 담당자별로 묶어 갱신 요청 메일을 발송한다.

    할당 태스크가 없는 담당자에게는 보내지 않는다.
    (success_count, total_assignee, results) 형태의 dict 반환.
    """
    project = get_project(project_id)
    if not project:
        return {'sent': 0, 'total': 0, 'results': [], 'error': '프로젝트 없음'}

    tasks = get_week_tasks(project_id)
    if not tasks:
        return {'sent': 0, 'total': 0, 'results': []}

    by_assignee = {}
    for item in tasks:
        name = (item.get('assignee') or '').strip()
        if not name:
            continue
        by_assignee.setdefault(name, []).append(item)

    if base_url is None:
        base_url = current_app.config.get('APP_BASE_URL') or 'http://localhost:5000'
    base_url = base_url.rstrip('/')
    project_url = f"{base_url}/project/{project_id}/wbs"

    db = get_db()
    results = []
    sent_count = 0
    for assignee_name, assigned in by_assignee.items():
        user_row = db.execute(
            "SELECT email FROM user WHERE name = ?", (assignee_name,)
        ).fetchone()
        if not user_row or not user_row['email']:
            results.append({'assignee': assignee_name, 'success': False, 'message': '등록된 이메일 없음'})
            continue

        html = build_task_update_mail_html(assignee_name, assigned, project['name'], project_url)
        ok, msg = send_html_mail(
            to_address=user_row['email'],
            to_name=assignee_name,
            subject=f"[WBS 알림] {project['name']} 이번주 태스크 {len(assigned)}건 갱신 요청",
            html_body=html,
        )
        results.append({
            'assignee': assignee_name,
            'email': user_row['email'],
            'count': len(assigned),
            'success': ok,
            'message': msg,
        })
        if ok:
            sent_count += 1

    return {'sent': sent_count, 'total': len(by_assignee), 'results': results}

from flask import Blueprint, g, jsonify, request, session

from app.auth import api_login_required, project_access_required
from app.models import wbs_item as wbs_model
from app.services import dashboard_service, wbs_service
from app.services.ai_assistant import process_command as ai_process_command
from app.services.auth_service import get_project_role

api_wbs_bp = Blueprint('api_wbs', __name__)


def _check_item_write(item_id):
    """항목 ID로부터 프로젝트 접근 권한을 확인한다. (participant 이상)"""
    item = wbs_model.get_item(item_id)
    if not item:
        return None, jsonify({'error': '항목을 찾을 수 없습니다.'}), 404
    role = get_project_role(session['user_id'], item['project_id'])
    if not role or role == 'viewer':
        return None, jsonify({'error': '권한이 부족합니다.'}), 403
    return item, None, None


# --- WBS 항목 CRUD ---

@api_wbs_bp.route('/<int:project_id>/items', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def list_items(project_id):
    mode = request.args.get('mode', 'flat')
    if mode == 'tree':
        items = wbs_service.get_tree(project_id)
    else:
        items = wbs_service.get_flat_list(project_id)
    return jsonify(items)


@api_wbs_bp.route('/<int:project_id>/items', methods=['POST'])
@api_login_required
@project_access_required('developer')
def create_item(project_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': '데이터가 없습니다.'}), 400
    data['project_id'] = project_id
    item = wbs_service.create_item(data)
    return jsonify(item), 201


@api_wbs_bp.route('/items/<int:item_id>', methods=['GET'])
@api_login_required
def get_item(item_id):
    item = wbs_model.get_item(item_id)
    if not item:
        return jsonify({'error': '항목을 찾을 수 없습니다.'}), 404
    return jsonify(item)


@api_wbs_bp.route('/items/<int:item_id>', methods=['PUT'])
@api_login_required
def update_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    if not data:
        return jsonify({'error': '수정할 데이터가 없습니다.'}), 400
    result = wbs_service.update_item(item_id, data, updated_by=session.get('user_name', ''))
    return jsonify(result)


@api_wbs_bp.route('/items/<int:item_id>', methods=['PATCH'])
@api_login_required
def patch_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    if not data:
        return jsonify({'error': '수정할 데이터가 없습니다.'}), 400
    result = wbs_service.update_item(item_id, data, updated_by=session.get('user_name', ''))
    return jsonify(result)


@api_wbs_bp.route('/items/<int:item_id>', methods=['DELETE'])
@api_login_required
def delete_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    wbs_service.delete_item(item_id)
    return jsonify({'message': '항목이 삭제되었습니다.'})


# --- 이동/순서변경 ---

@api_wbs_bp.route('/items/<int:item_id>/move', methods=['POST'])
@api_login_required
def move_item(item_id):
    item, *err = _check_item_write(item_id)
    if err[0]:
        return err[0], err[1]
    data = request.get_json()
    result = wbs_service.move_item(item_id, data.get('parent_id'), data.get('sort_order', 0))
    return jsonify(result)


@api_wbs_bp.route('/<int:project_id>/items/batch', methods=['POST'])
@api_login_required
@project_access_required('developer')
def batch_update(project_id):
    data = request.get_json()
    if not data or not isinstance(data.get('items'), list):
        return jsonify({'error': '항목 목록이 필요합니다.'}), 400
    results = wbs_service.batch_update(project_id, data['items'], updated_by=session.get('user_name', ''))
    return jsonify(results)


# --- 데이터 초기화 ---

@api_wbs_bp.route('/<int:project_id>/items', methods=['DELETE'])
@api_login_required
@project_access_required('developer')
def clear_items(project_id):
    from app.extensions import get_db
    db = get_db()
    db.execute("DELETE FROM wbs_item WHERE project_id = ?", (project_id,))
    db.commit()
    return jsonify({'message': '모든 WBS 항목이 초기화되었습니다.'})


# --- 통계 ---

@api_wbs_bp.route('/<int:project_id>/stats', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_stats(project_id):
    stats = wbs_service.get_stats(project_id)
    return jsonify(stats)


@api_wbs_bp.route('/<int:project_id>/weekly-stats', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_weekly_stats(project_id):
    """주차별 WBS 진척 통계를 반환한다."""
    num_weeks = min(int(request.args.get('weeks', 8)), 26)
    result = wbs_service.get_weekly_stats(project_id, num_weeks=num_weeks)
    return jsonify(result)


@api_wbs_bp.route('/<int:project_id>/delayed', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_delayed(project_id):
    items = dashboard_service.get_delayed_items(project_id)
    return jsonify(items)


@api_wbs_bp.route('/<int:project_id>/dashboard', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def get_dashboard(project_id):
    return jsonify({
        'overview': dashboard_service.get_overview(project_id),
        'by_category': dashboard_service.get_progress_by_category(project_id),
        'by_assignee': dashboard_service.get_assignee_workload(project_id),
        'timeline': dashboard_service.get_timeline_data(project_id),
    })


# --- 일정 지연 분석 ---

@api_wbs_bp.route('/<int:project_id>/schedule-gaps', methods=['GET'])
@api_login_required
@project_access_required('viewer')
def schedule_gaps(project_id):
    """계획일 vs 실제일 차이가 있는 항목을 지연일수와 함께 반환한다."""
    from app.services.ai_assistant import analyze_schedule_gaps
    result = analyze_schedule_gaps(project_id)
    return jsonify(result)


# --- 지연 태스크 메일 발송 ---

@api_wbs_bp.route('/<int:project_id>/send-delay-mail', methods=['POST'])
@api_login_required
@project_access_required('admin')
def send_delay_mail(project_id):
    """지연 태스크를 각 담당자에게 이메일로 알림 발송한다."""
    from app.extensions import get_db
    from app.models.project import get_project
    from app.services.mail_service import build_delay_mail_html, send_html_mail

    project = get_project(project_id)
    if not project:
        return jsonify({'error': '프로젝트를 찾을 수 없습니다.'}), 404

    delayed = dashboard_service.get_delayed_items(project_id)
    if not delayed:
        return jsonify({'message': '지연된 태스크가 없습니다.', 'sent': 0, 'results': []})

    # 담당자별 그룹화
    by_assignee = {}
    for item in delayed:
        name = (item.get('assignee') or '').strip()
        if not name:
            continue
        by_assignee.setdefault(name, []).append(item)

    db = get_db()
    base_url = request.host_url.rstrip('/')
    project_url = f"{base_url}/project/{project_id}/wbs"

    results = []
    sent_count = 0
    for assignee_name, tasks in by_assignee.items():
        user_row = db.execute(
            "SELECT email FROM user WHERE name = ?", (assignee_name,)
        ).fetchone()
        if not user_row or not user_row['email']:
            results.append({'assignee': assignee_name, 'success': False, 'message': '등록된 이메일 없음'})
            continue

        html = build_delay_mail_html(assignee_name, tasks, project['name'], project_url)
        ok, msg = send_html_mail(
            to_address=user_row['email'],
            to_name=assignee_name,
            subject=f"[WBS 알림] {project['name']} 지연 태스크 {len(tasks)}건",
            html_body=html,
        )
        results.append({
            'assignee': assignee_name,
            'email': user_row['email'],
            'count': len(tasks),
            'success': ok,
            'message': msg,
        })
        if ok:
            sent_count += 1

    return jsonify({'sent': sent_count, 'total': len(by_assignee), 'results': results})


# --- AI 어시스턴트 ---

@api_wbs_bp.route('/<int:project_id>/ai', methods=['POST'])
@api_login_required
@project_access_required('admin')
def ai_assistant(project_id):
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({'success': False, 'message': '질의를 입력해주세요.'}), 400

    user_query = data['query'].strip()
    role = get_project_role(session['user_id'], project_id)

    # viewer는 조회만 가능
    result = ai_process_command(project_id, user_query)
    if role == 'viewer' and result.get('action') in ('add', 'delete', 'update'):
        return jsonify({'success': False, 'message': '읽기 전용 권한으로는 데이터를 변경할 수 없습니다.'}), 403

    return jsonify(result)

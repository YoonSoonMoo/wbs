"""WBS AI Assistant — Claude CLI를 활용한 자연어 명령 처리

자연어 입력을 파싱하여 WBS 데이터 조회/추가/삭제 명령으로 변환하고 실행한다.
template/claude_query_parser.py의 패턴을 참고하여 구현.
"""
import json
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta

from app.extensions import get_db
from app.models import wbs_item as wbs_model
from app.services import wbs_service

logger = logging.getLogger(__name__)

_is_windows = sys.platform == "win32"


def _call_claude(system_prompt: str, user_prompt: str) -> str:
    """Claude Code CLI를 subprocess로 호출한다."""
    full_prompt = f"[시스템 지시사항]\n{system_prompt}\n\n[사용자 요청]\n{user_prompt}"
    try:
        result = subprocess.run(
            "claude -p --max-turns 1",
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            shell=_is_windows,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude CLI 오류: {result.stderr.strip()}")
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("claude CLI가 빈 응답을 반환했습니다")
        return output
    except FileNotFoundError:
        raise RuntimeError("claude CLI가 설치되어 있지 않습니다")
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI 호출 타임아웃 (120초)")


def _parse_json_response(text: str) -> dict:
    """Claude 응답에서 JSON을 추출한다."""
    content = text.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def _build_system_prompt(items_summary: str) -> str:
    """자연어 → WBS 명령 변환용 시스템 프롬프트를 생성한다."""
    today = datetime.now().strftime('%Y-%m-%d')
    return f"""당신은 WBS(Work Breakdown Structure) 관리 AI 어시스턴트입니다.
사용자의 자연어 요청을 분석하여 아래 JSON 형식으로 응답하세요.

## 현재 날짜
{today}

## WBS 컬럼 정보
- category: 구분 (기획, 설계, 개발, QA 등)
- task_name: Task명
- subtask: 서브태스크
- detail: 세부항목
- assignee: 담당자
- plan_start: 계획시작일 (YYYY-MM-DD)
- plan_end: 계획완료일 (YYYY-MM-DD)
- actual_start: 실제시작일
- actual_end: 실제종료일
- effort: 공수 (숫자)
- progress: 진행률 (0~100)
- status: 진행상태 (담당자가 자유롭게 기입하는 텍스트. 리스크, 이슈, 지연사유, 진행메모 등이 포함될 수 있음)

## 현재 WBS 데이터 요약
{items_summary}

## 명령 타입
1. **query** — 조건에 맞는 항목 조회/필터링
2. **add** — 새 항목 추가
3. **delete** — 항목 삭제
4. **update** — 항목 수정

## 응답 형식 (JSON만 반환, 코드블록 없이)

### query 타입 예시:
{{
    "action": "query",
    "filters": {{"assignee": "이필원", "progress": 100}},
    "description": "담당자가 이필원이고 완료된 업무 목록입니다.",
    "insight": "이필원님은 총 N건의 업무를 완료했으며 일정 준수율이 높습니다."
}}

참고: query 결과에는 자동으로 summary(count, total_effort, avg_progress)가 포함됩니다.
사용자가 공수 합계, 평균 진행률 등 집계를 물어보면 query로 필터링하세요. 시스템이 자동 계산합니다.

※ insight 필드: 조회 결과에 대한 분석 코멘트를 작성하세요.
- 지연/문제 파악 시: 각 항목의 status(진행상태) 내용을 반드시 확인하고 리스크나 이슈를 언급
- 일정 차이 분석 시: 심각도별로 어떤 업무가 가장 위험한지 판단
- 종합적인 상황 판단과 추천 액션을 간결하게 제시
- insight가 불필요한 단순 조회는 생략 가능

filters에 사용 가능한 특수 키:
- "delayed": true — 계획완료일이 지났는데 미완료인 항목 (진행중이지만 기한 초과)
- "schedule_delayed": true — 계획일 대비 실제 종료일이 늦은 항목 (완료 여부와 무관하게 일정 차이 발생)
- "schedule_gap_min": 숫자 — 종료 지연이 N일 이상인 항목 (예: 3이면 3일 이상 지연)
- "start_delayed": true — 실제 시작일이 계획 시작일보다 늦은 항목
- "date_diff": true — 계획일자와 실제일자가 다른 모든 항목 (시작 또는 종료)
- "detail_contains": "검색어" — 세부항목에 특정 텍스트 포함
- "progress_lt": 숫자 — 진행률이 특정 값 미만
- "progress_gte": 숫자 — 진행률이 특정 값 이상
- 일반 컬럼명: 해당 값과 일치

※ 일정 관련 중요 개념:
- 계획완료일(plan_end) vs 실제종료일(actual_end) 차이 = 일정 지연일수 (양수=지연, 음수=조기완료)
- 계획시작일(plan_start) vs 실제시작일(actual_start) 차이도 동일하게 계산
- "일정 지연", "일정 차이", "스케줄 갭" 등의 질의 → schedule_delayed 또는 date_diff 사용
- 결과에는 start_gap_days, end_gap_days 필드가 포함됨 (지연일수)

### add 타입 예시:
{{
    "action": "add",
    "data": {{
        "task_name": "상품 정보 관리 기능",
        "subtask": "개발",
        "assignee": "조민기",
        "plan_start": "2026-04-22",
        "plan_end": "2026-04-23",
        "effort": 2
    }},
    "description": "새 항목을 추가했습니다."
}}

### delete 타입 예시 (행 번호 기준):
{{
    "action": "delete",
    "row_number": 11,
    "description": "11번 행을 삭제합니다."
}}

### update 타입 예시:
{{
    "action": "update",
    "row_number": 5,
    "data": {{"progress": 80, "status": "진행중"}},
    "description": "5번 행의 진행률을 80%로 수정했습니다."
}}

중요: JSON만 응답하세요. 코드블록으로 감싸지 마세요. 날짜는 반드시 YYYY-MM-DD 형식을 사용하세요.
4/22 같은 형식은 올해 기준으로 2026-04-22 로 변환하세요."""


def _get_items_summary(project_id: int) -> str:
    """현재 WBS 데이터의 요약을 문자열로 반환한다."""
    items = wbs_model.get_flat_items(project_id)
    if not items:
        return "항목 없음"

    lines = []
    for i, item in enumerate(items):
        row_num = i + 1
        name = item.get('task_name', '') or ''
        sub = item.get('subtask', '') or ''
        assignee = item.get('assignee', '') or ''
        progress = item.get('progress', 0) or 0
        plan_end = item.get('plan_end', '') or ''
        actual_end = item.get('actual_end', '') or ''
        detail = (item.get('detail', '') or '')[:30]
        sched = _compute_schedule_info(item)
        gap_info = ''
        if sched['end_gap_days'] is not None and sched['end_gap_days'] != 0:
            gap_info = f" 종료갭:{sched['end_gap_days']:+d}일"
        status = (item.get('status', '') or '')[:40]
        lines.append(
            f"  {row_num}. [{name}] 서브:{sub} 담당:{assignee} "
            f"진행:{progress}% 계획완료:{plan_end} 실제종료:{actual_end}{gap_info} 상태:{status} 세부:{detail}"
        )
    return f"총 {len(items)}건:\n" + "\n".join(lines)


def _calc_day_diff(date_a: str, date_b: str) -> int:
    """두 날짜 문자열(YYYY-MM-DD)의 차이를 일수로 반환한다. date_b - date_a."""
    try:
        a = datetime.strptime(date_a, '%Y-%m-%d').date()
        b = datetime.strptime(date_b, '%Y-%m-%d').date()
        return (b - a).days
    except (ValueError, TypeError):
        return 0


def _compute_schedule_info(item: dict) -> dict:
    """항목의 일정 차이 정보를 계산한다.

    종료 지연 판단:
    - 실제종료일이 있으면: 실제종료일 - 계획완료일
    - 실제종료일이 없으면 미완료 업무이므로: 오늘 - 계획완료일 (양수면 지연 중)
    시작도 동일한 로직 적용.
    """
    ps = (item.get('plan_start', '') or '').strip()
    pe = (item.get('plan_end', '') or '').strip()
    a_s = (item.get('actual_start', '') or '').strip()
    ae = (item.get('actual_end', '') or '').strip()
    today = datetime.now().strftime('%Y-%m-%d')
    progress = int(item.get('progress', 0) or 0)

    start_gap = _calc_day_diff(ps, a_s) if (ps and a_s) else None

    if pe and ae:
        # 완료된 업무: 실제종료일 - 계획완료일
        end_gap = _calc_day_diff(pe, ae)
    elif pe and not ae and progress < 100:
        # 미완료 업무: 오늘 - 계획완료일 (양수면 현재 지연 중)
        end_gap = _calc_day_diff(pe, today)
        if end_gap <= 0:
            end_gap = None  # 아직 기한 전이면 갭 없음
    else:
        end_gap = None

    return {
        'start_gap_days': start_gap,  # 양수 = 실제가 늦음, 음수 = 실제가 빠름
        'end_gap_days': end_gap,
        'has_start_delay': start_gap is not None and start_gap > 0,
        'has_end_delay': end_gap is not None and end_gap > 0,
    }


def analyze_schedule_gaps(project_id: int) -> dict:
    """프로젝트 전체 일정 차이 분석 결과를 반환한다 (API용)."""
    items = wbs_model.get_flat_items(project_id)
    results = []

    for i, item in enumerate(items):
        info = _compute_schedule_info(item)
        if info['start_gap_days'] is not None or info['end_gap_days'] is not None:
            results.append({
                **item,
                '_row_number': i + 1,
                'start_gap_days': info['start_gap_days'],
                'end_gap_days': info['end_gap_days'],
            })

    # 지연(종료 기준) 항목만 분리
    delayed = [r for r in results if (r.get('end_gap_days') or 0) > 0]
    early = [r for r in results if (r.get('end_gap_days') or 0) < 0]
    on_time = [r for r in results if r.get('end_gap_days') == 0]

    return {
        'total_with_dates': len(results),
        'delayed_count': len(delayed),
        'early_count': len(early),
        'on_time_count': len(on_time),
        'items': results,
        'delayed_items': delayed,
    }


def _execute_query(project_id: int, filters: dict) -> dict:
    """필터 조건에 맞는 WBS 항목을 조회한다."""
    items = wbs_model.get_flat_items(project_id)
    today = datetime.now().strftime('%Y-%m-%d')
    results = []

    for i, item in enumerate(items):
        match = True
        sched = _compute_schedule_info(item)

        for key, val in filters.items():
            if key == 'delayed':
                plan_end = item.get('plan_end', '')
                progress = int(item.get('progress', 0) or 0)
                if not (plan_end and plan_end < today and progress < 100):
                    match = False
            elif key == 'date_diff':
                if not (sched['start_gap_days'] is not None and sched['start_gap_days'] != 0) \
                   and not (sched['end_gap_days'] is not None and sched['end_gap_days'] != 0):
                    match = False
            elif key == 'schedule_delayed':
                # 계획 대비 실제 일정이 늦은 항목 (종료일 기준)
                if not sched['has_end_delay']:
                    match = False
            elif key == 'schedule_gap_min':
                # 종료 지연이 N일 이상인 항목
                gap = sched['end_gap_days']
                if gap is None or gap < int(val):
                    match = False
            elif key == 'start_delayed':
                # 시작일이 계획보다 늦은 항목
                if not sched['has_start_delay']:
                    match = False
            elif key == 'detail_contains':
                detail = (item.get('detail', '') or '').lower()
                if val.lower() not in detail:
                    match = False
            elif key == 'progress_lt':
                if int(item.get('progress', 0) or 0) >= int(val):
                    match = False
            elif key == 'progress_gte':
                if int(item.get('progress', 0) or 0) < int(val):
                    match = False
            elif key in ('category', 'task_name', 'subtask', 'assignee', 'status'):
                item_val = (item.get(key, '') or '').strip()
                if item_val != str(val).strip():
                    match = False
            elif key == 'progress':
                if int(item.get('progress', 0) or 0) != int(val):
                    match = False

        if match:
            row = {**item, '_row_number': i + 1}
            row['start_gap_days'] = sched['start_gap_days']
            row['end_gap_days'] = sched['end_gap_days']
            results.append(row)

    # 집계 통계 계산
    total_effort = sum(float(r.get('effort', 0) or 0) for r in results)
    avg_progress = (sum(int(r.get('progress', 0) or 0) for r in results) / len(results)) if results else 0
    summary = {
        'count': len(results),
        'total_effort': round(total_effort, 1),
        'avg_progress': round(avg_progress, 1),
    }

    return {'items': results, 'count': len(results), 'summary': summary}


def _execute_add(project_id: int, data: dict) -> dict:
    """새 WBS 항목을 추가한다."""
    data['project_id'] = project_id
    item = wbs_service.create_item(data)
    return {'item': item}


def _execute_delete(project_id: int, row_number: int) -> dict:
    """행 번호로 WBS 항목을 삭제한다."""
    items = wbs_model.get_flat_items(project_id)
    idx = row_number - 1
    if idx < 0 or idx >= len(items):
        return {'error': f'{row_number}번 행이 존재하지 않습니다.'}

    item = items[idx]
    wbs_service.delete_item(item['id'])
    return {'deleted_id': item['id'], 'task_name': item.get('task_name', '')}


def _execute_update(project_id: int, row_number: int, data: dict) -> dict:
    """행 번호로 WBS 항목을 수정한다."""
    items = wbs_model.get_flat_items(project_id)
    idx = row_number - 1
    if idx < 0 or idx >= len(items):
        return {'error': f'{row_number}번 행이 존재하지 않습니다.'}

    item = items[idx]
    updated = wbs_service.update_item(item['id'], data)
    return {'item': updated}


def process_command(project_id: int, user_input: str) -> dict:
    """자연어 입력을 파싱하고 실행하여 결과를 반환한다."""
    items_summary = _get_items_summary(project_id)
    system_prompt = _build_system_prompt(items_summary)
    user_prompt = f'질의: "{user_input}"\nJSON 형식으로만 응답하세요. 코드블록으로 감싸지 마세요.'

    try:
        response_text = _call_claude(system_prompt, user_prompt)
        parsed = _parse_json_response(response_text)

        if not parsed or 'action' not in parsed:
            return {
                'success': False,
                'message': '명령을 이해하지 못했습니다. 다시 시도해주세요.',
                'raw': response_text[:500],
            }

        action = parsed['action']
        description = parsed.get('description', '')

        if action == 'query':
            result = _execute_query(project_id, parsed.get('filters', {}))
            resp = {
                'success': True,
                'action': 'query',
                'message': description,
                'data': result,
            }
            if parsed.get('insight'):
                resp['insight'] = parsed['insight']
            return resp

        elif action == 'add':
            result = _execute_add(project_id, parsed.get('data', {}))
            return {
                'success': True,
                'action': 'add',
                'message': description,
                'data': result,
            }

        elif action == 'delete':
            row_num = parsed.get('row_number', 0)
            result = _execute_delete(project_id, row_num)
            if 'error' in result:
                return {'success': False, 'message': result['error']}
            return {
                'success': True,
                'action': 'delete',
                'message': description,
                'data': result,
            }

        elif action == 'update':
            row_num = parsed.get('row_number', 0)
            result = _execute_update(project_id, row_num, parsed.get('data', {}))
            if 'error' in result:
                return {'success': False, 'message': result['error']}
            return {
                'success': True,
                'action': 'update',
                'message': description,
                'data': result,
            }

        else:
            return {'success': False, 'message': f'알 수 없는 명령: {action}'}

    except RuntimeError as e:
        logger.error(f"AI 어시스턴트 오류: {e}")
        return {'success': False, 'message': str(e)}
    except Exception as e:
        logger.error(f"AI 어시스턴트 처리 실패: {e}", exc_info=True)
        return {'success': False, 'message': '처리 중 오류가 발생했습니다.'}

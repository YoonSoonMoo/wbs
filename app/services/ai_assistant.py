"""WBS AI Assistant — Claude CLI를 활용한 자연어 명령 처리

자연어 입력을 파싱하여 WBS 데이터 조회/추가/삭제 명령으로 변환하고 실행한다.
template/claude_query_parser.py의 패턴을 참고하여 구현.
"""
import json
import logging
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta

from flask import current_app

from app.extensions import get_db
from app.models import project as project_model
from app.models import wbs_item as wbs_model
from app.services import wbs_service
from app.services.wbs_code_service import recalculate_codes

logger = logging.getLogger(__name__)

_is_windows = sys.platform == "win32"

# GEMINI(AI_MODEL=GEMINI)에서 AI_BASE_URL 미설정 시 사용하는 OpenAI 호환 기본 엔드포인트
_GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# 사내 GEMMA(llama.cpp) 슬롯 할당: 0=기술지원, 1=AI 모니터링, 2=WBS(고정)
_GEMMA_ID_SLOT = 2


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """AI_MODEL 설정에 따라 LLM을 호출한다.

    GEMINI/GEMMA → OpenAI 호환 엔드포인트, LOCAL → claude -p CLI.
    """
    provider = current_app.config.get("AI_MODEL", "LOCAL")
    if provider in ("GEMINI", "GEMMA"):
        return _call_openai_compatible(system_prompt, user_prompt)
    return _call_claude_cli(system_prompt, user_prompt)


def _call_openai_compatible(system_prompt: str, user_prompt: str) -> str:
    """OpenAI 호환 엔드포인트(사내 LiteLLM/GEMMA, Gemini)를 호출한다."""
    from openai import OpenAI

    cfg = current_app.config
    provider = cfg.get("AI_MODEL")
    base_url = cfg.get("AI_BASE_URL") or _GEMINI_DEFAULT_BASE_URL
    # GEMMA(사내 llama.cpp)는 컨텍스트가 작아(예: 4096) 출력 토큰이 입력+출력 합을
    # 초과하지 않도록 제한. 응답 JSON은 짧아 1024로 충분하다.
    max_tokens = 1024 if provider == "GEMMA" else 2048
    # GEMMA(llama.cpp)는 지정 슬롯의 KV 캐시를 쓰도록 id_slot을 고정 전달한다.
    # Gemini 등 다른 OpenAI 호환 엔드포인트엔 미지원 파라미터라 보내지 않는다.
    create_kwargs = {}
    if provider == "GEMMA":
        create_kwargs["extra_body"] = {"id_slot": _GEMMA_ID_SLOT}
    try:
        client = OpenAI(base_url=base_url, api_key=cfg["AI_API_KEY"])
        resp = client.chat.completions.create(
            model=cfg["AI_MODEL_NAME"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=max_tokens,
            **create_kwargs,
        )
        choice = resp.choices[0]
        output = (choice.message.content or "").strip()
        if not output:
            # 빈 응답 원인 진단: finish_reason='length' + completion_tokens=0 이면
            # 입력이 컨텍스트 천장에 붙어 생성 여유가 없는 것(프롬프트 축소/ctx 상향 필요).
            usage = getattr(resp, "usage", None)
            detail = f"finish_reason={getattr(choice, 'finish_reason', None)}"
            if usage is not None:
                detail += (f", prompt_tokens={getattr(usage, 'prompt_tokens', None)}"
                           f", completion_tokens={getattr(usage, 'completion_tokens', None)}")
            raise RuntimeError(f"LLM이 빈 응답을 반환했습니다 ({detail})")
        return output
    except Exception as e:
        raise RuntimeError(f"LLM 호출 오류({cfg.get('AI_MODEL')}): {e}")


def _call_claude_cli(system_prompt: str, user_prompt: str) -> str:
    """Claude Code CLI를 subprocess로 호출한다 (AI_MODEL=LOCAL)."""
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


def _build_system_prompt(items_summary: str, project_overview: str = "") -> str:
    """자연어 → WBS 명령 변환용 시스템 프롬프트를 생성한다."""
    today = datetime.now().strftime('%Y-%m-%d')
    overview_block = project_overview if project_overview else "(프로젝트 개요 미기입)"
    return f"""당신은 WBS(Work Breakdown Structure) 관리 AI 어시스턴트이자 PM 자문역입니다.
사용자의 자연어 요청을 분석하여 아래 JSON 형식으로 응답하세요.

## 현재 날짜
{today}

## 프로젝트 개요 (PM이 기입한 전체 개요 · 목적 · 마일스톤 · 리스크)
{overview_block}

※ "프로젝트 분석", "프로젝트 전반적인 진척상황", "전반 상황", "리스크 점검", "PM 관점 조언"
   등 프로젝트 전체를 묻는 질의에는 위 **프로젝트 개요**와 아래 WBS 데이터를 함께 참고하여
   insight 필드에 전반 상황 판단과 PM을 위한 조언(마일스톤 대비 진척, 주요 지연/리스크, 권장 액션)을
   반드시 작성하세요. 개요가 비어 있다면 WBS 데이터만으로 판단하되, 개요가 없어 근거가 제한적임을
   함께 언급하세요.

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
5. **move** — 행 순서 이동 (TID/행 번호 기준)

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
- "schedule_early": true — 계획완료일보다 일찍 종료된 항목 (조기완료, end_gap_days < 0). "먼저 끝난", "일찍 종료", "조기완료" 질의에 사용
- "start_delayed": true — 실제 시작일이 계획 시작일보다 늦은 항목 (지연착수, start_gap_days > 0). "늦게 시작", "착수 지연", "지연착수" 질의에 사용
- "start_early": true — 실제 시작일이 계획 시작일보다 이른 항목 (선착수, start_gap_days < 0). "선착수", "먼저 착수", "일찍 시작" 질의에 사용. ※ actual_start < plan_start 일 때만 해당하며, 같은 날이면 제외
- "date_diff": true — 계획일자와 실제일자가 다른 모든 항목 (시작 또는 종료)
- "detail_contains": "검색어" — 세부항목에 특정 텍스트 포함
- "progress_lt": 숫자 — 진행률이 특정 값 미만
- "progress_gte": 숫자 — 진행률이 특정 값 이상
- 일반 컬럼명: 해당 값과 일치

※ 일정 관련 중요 개념:
- 계획완료일(plan_end) vs 실제종료일(actual_end) 차이 = end_gap_days (양수=지연, 음수=조기완료)
- 계획시작일(plan_start) vs 실제시작일(actual_start) 차이 = start_gap_days (양수=지연착수, 음수=선착수)
- **선착수(早着手)** = actual_start < plan_start (계획보다 먼저 착수) → start_early 사용
- **지연착수** = actual_start > plan_start (계획보다 늦게 착수) → start_delayed 사용
- actual_start == plan_start 는 선착수도 지연착수도 아님 (정시 착수, 제외)
- "일정 지연", "일정 차이", "스케줄 갭" 등의 질의 → schedule_delayed 또는 date_diff 사용
- 결과에는 start_gap_days, end_gap_days 필드가 포함됨

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

### move 타입 예시 (TID/행 번호 기준 순서 이동):
{{
    "action": "move",
    "source_row": 43,
    "target_row": 326,
    "position": "above",
    "description": "TID 43번을 326번 위로 이동했습니다."
}}

※ "TID"는 화면 좌측에 표시되는 행 번호와 동일하다 (1-base, 위 WBS 데이터 요약의 1., 2., 3. 번호).
※ position 값:
  - "above" — 대상 행 바로 위로 이동. "위로", "앞으로", "before" 표현에 사용 (기본값).
  - "below" — 대상 행 바로 아래로 이동. "아래로", "뒤로", "after" 표현에 사용.
※ 예: "43번을 326번 위로 이동" → source_row=43, target_row=326, position="above".
※ 예: "10번을 5번 아래로" → source_row=10, target_row=5, position="below".

중요: JSON만 응답하세요. 코드블록으로 감싸지 마세요. 날짜는 반드시 YYYY-MM-DD 형식을 사용하세요.
4/22 같은 형식은 올해 기준으로 2026-04-22 로 변환하세요."""


def _get_project_overview(project_id: int) -> str:
    """프로젝트 메타정보(이름·기간·설명)를 문자열 개요로 반환한다.

    description 은 PM이 기입한 프로젝트 전체 개요·마일스톤·리스크 등을 담는 필드다.
    AI가 전반 상황을 추론하는 근거로 사용된다.
    """
    project = project_model.get_project(project_id)
    if not project:
        return ""

    name = (project.get('name') or '').strip()
    desc = (project.get('description') or '').strip()
    start = (project.get('start_date') or '').strip()
    end = (project.get('end_date') or '').strip()
    period = f"{start or '미정'} ~ {end or '미정'}"

    parts = [f"- 프로젝트명: {name or '(이름 없음)'}", f"- 기간: {period}"]
    if desc:
        parts.append("- 개요/마일스톤 (PM 기입):")
        parts.append(desc)
    else:
        parts.append("- 개요/마일스톤: (미기입)")
    return "\n".join(parts)


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


def _parse_date(value) -> "date | None":
    """'YYYY-MM-DD' 문자열을 date로 파싱한다. 실패 시 None."""
    s = (value or '').strip()
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


# 압축 요약에서 섹션별로 나열할 최대 항목 수 (초과분은 "...외 N건"으로 표기)
_COMPACT_DELAYED_CAP = 12
_COMPACT_WEEK_CAP = 30


def _get_compact_summary(project_id: int) -> str:
    """작은 컨텍스트 모델(GEMMA)용 요약.

    전체 행을 나열하면 컨텍스트(예: 4096토큰)를 초과하므로, 완료 항목을 제외하고
    ①기한경과·미완료(지연), ②이번주·다음주(오늘 기준 월~다음주 일, 14일) 계획기간이
    겹치는 미완료 항목만 핵심 필드(서브태스크/세부항목/담당자/계획시작/진행률/진행상태)와
    함께 추린다. 집계 헤더는 전체 건수만 제공. query 필터는 LLM이 생성하고 실제 조회는
    _execute_query가 전체 데이터로 수행하므로 결과 정확도는 유지되며, insight는 아래
    요약을 근거로 작성된다.
    """
    items = wbs_model.get_flat_items(project_id)
    if not items:
        return "항목 없음"

    total = len(items)
    done = sum(1 for it in items if (it.get('progress') or 0) >= 100)
    in_prog = sum(1 for it in items if 0 < (it.get('progress') or 0) < 100)
    not_started = total - done - in_prog
    avg_progress = round(sum(it.get('progress') or 0 for it in items) / total)

    assignee_counts = Counter(((it.get('assignee') or '').strip() or '미지정') for it in items)
    assignee_str = ", ".join(f"{a}({c})" for a, c in assignee_counts.most_common())

    categories = sorted({(it.get('category') or '').strip() for it in items if (it.get('category') or '').strip()})
    category_str = ", ".join(categories) if categories else "(없음)"

    today = date.today()
    week_start = today - timedelta(days=today.weekday())   # 이번주 월요일
    week_end = week_start + timedelta(days=13)              # 다음주 일요일

    def _line(tid, item, tail):
        sub = (item.get('subtask') or '')
        assignee = (item.get('assignee') or '')
        ps = (item.get('plan_start') or '')
        prog = item.get('progress') or 0
        status = (item.get('status') or '')[:30]
        detail = (item.get('detail') or '')[:30]
        return (f"  TID{tid}. 서브:{sub} 담당:{assignee} 계획시작:{ps} 진행:{prog}% "
                f"상태:{status} 세부:{detail}{tail}")

    delayed = []   # (gap, line)
    week = []      # (sort_key, line)
    for i, item in enumerate(items):
        if (item.get('progress') or 0) >= 100:
            continue  # 완료 제외
        tid = i + 1
        sched = _compute_schedule_info(item)
        if sched['has_end_delay']:
            gap = sched['end_gap_days']
            delayed.append((gap, _line(tid, item, f" [지연{gap}일·계획완료:{item.get('plan_end') or ''}]")))
        # 이번주·다음주 윈도우와 계획기간 겹침 (start<=winEnd AND end>=winStart)
        ps_d = _parse_date(item.get('plan_start'))
        pe_d = _parse_date(item.get('plan_end'))
        s = ps_d or pe_d
        e = pe_d or ps_d
        if s and e and s <= week_end and e >= week_start:
            week.append((s, _line(tid, item, "")))

    def _block(rows, cap):
        rows_sorted = [ln for _, ln in rows]
        shown = rows_sorted[:cap]
        more = len(rows_sorted) - len(shown)
        if not shown:
            return "  (없음)"
        block = "\n".join(shown)
        if more > 0:
            block += f"\n  ...외 {more}건"
        return block

    delayed.sort(key=lambda x: x[0], reverse=True)
    week.sort(key=lambda x: x[0])

    return (
        f"총 {total}건 (완료 {done} / 진행중 {in_prog} / 미착수 {not_started}, 평균진행률 {avg_progress}%)\n"
        f"담당자별 건수: {assignee_str}\n"
        f"구분 목록: {category_str}\n"
        f"[지연] 기한경과·미완료 {len(delayed)}건:\n{_block(delayed, _COMPACT_DELAYED_CAP)}\n"
        f"[이번주·다음주] 미완료 {len(week)}건 (윈도우 {week_start}~{week_end}):\n{_block(week, _COMPACT_WEEK_CAP)}"
    )


def _build_compact_system_prompt(items_summary: str, project_overview: str = "") -> str:
    """작은 컨텍스트 모델(GEMMA)용 축약 시스템 프롬프트.

    _build_system_prompt와 동일한 JSON 프로토콜·필터 키를 유지하되, 장황한 설명/예시를
    덜어내 토큰을 절약한다(한글은 llama.cpp 계열 토크나이저에서 토큰 수가 크다).
    """
    today = datetime.now().strftime('%Y-%m-%d')
    year = today[:4]
    overview_block = project_overview if project_overview else "(미기입)"
    return f"""당신은 WBS 관리 AI 어시스턴트입니다. 사용자 질의를 분석해 JSON만 반환하세요(코드블록 금지).

오늘: {today}

프로젝트 개요:
{overview_block}

WBS 현황 요약:
{items_summary}

## 명령(action)
- query 조회: {{"action":"query","filters":{{...}},"description":"...","insight":"(선택)분석코멘트"}}
- add 추가: {{"action":"add","data":{{"task_name":"...","subtask":"...","assignee":"...","plan_start":"YYYY-MM-DD","plan_end":"YYYY-MM-DD","effort":2}},"description":"..."}}
- delete 삭제: {{"action":"delete","row_number":11,"description":"..."}}
- update 수정: {{"action":"update","row_number":5,"data":{{"progress":80,"status":"진행중"}},"description":"..."}}
- move 순서이동: {{"action":"move","source_row":43,"target_row":326,"position":"above","description":"..."}}

## filters 키
- 일반 컬럼(assignee, category, status, progress 등): 값 일치
- delayed:true(기한경과·미완료) / schedule_delayed:true(실제종료 지연) / schedule_gap_min:N(N일이상 지연)
- schedule_early:true(조기완료) / start_delayed:true(지연착수) / start_early:true(선착수) / date_diff:true(계획·실제 불일치)
- detail_contains:"키워드"(세부항목 포함) / progress_lt:N(진행률 미만) / progress_gte:N(진행률 이상)

규칙:
- row_number/source_row/target_row는 사용자가 말한 TID(1-base)를 그대로 사용.
- position은 "above"(위, 기본) 또는 "below"(아래).
- 날짜는 YYYY-MM-DD. "4/22"는 {year} 기준으로 변환.
- 전반 진척/리스크 질의는 위 현황 요약을 근거로 insight에 작성.
- JSON만, 코드블록 없이 응답."""


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
            elif key == 'schedule_early':
                # 계획완료일보다 일찍 종료된 항목 (조기완료)
                gap = sched['end_gap_days']
                if gap is None or gap >= 0:
                    match = False
            elif key == 'start_delayed':
                # 시작일이 계획보다 늦은 항목 (지연착수)
                if not sched['has_start_delay']:
                    match = False
            elif key == 'start_early':
                # 시작일이 계획보다 이른 항목 (선착수: actual_start < plan_start)
                gap = sched['start_gap_days']
                if gap is None or gap >= 0:
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


def _execute_move(project_id: int, source_row: int, target_row: int, position: str = 'above') -> dict:
    """TID(행 번호) 기준으로 항목을 이동하고 sort_order 를 재정렬한다.

    드래그앤드롭과 동일한 시맨틱:
    - 전역 flat 리스트(sort_order 정렬) 기준으로 source 를 빼고 target 위/아래에 삽입
    - 모든 항목의 sort_order 를 0..N-1 로 재할당
    - parent_id 는 변경하지 않음 (기존 드래그 동작과 동일)
    """
    try:
        source_row = int(source_row)
        target_row = int(target_row)
    except (TypeError, ValueError):
        return {'error': 'source_row / target_row 는 정수여야 합니다.'}

    pos = (position or 'above').lower()
    if pos not in ('above', 'below'):
        pos = 'above'

    items = wbs_model.get_flat_items(project_id)
    n = len(items)
    src_idx = source_row - 1
    tgt_idx = target_row - 1

    if src_idx < 0 or src_idx >= n:
        return {'error': f'TID {source_row}번이 존재하지 않습니다.'}
    if tgt_idx < 0 or tgt_idx >= n:
        return {'error': f'TID {target_row}번이 존재하지 않습니다.'}
    if src_idx == tgt_idx:
        return {'error': '원본과 대상 행이 동일합니다.'}

    moved = items.pop(src_idx)
    new_idx = tgt_idx
    if src_idx < tgt_idx:
        new_idx -= 1
    if pos == 'below':
        new_idx += 1
    new_idx = max(0, min(new_idx, len(items)))
    items.insert(new_idx, moved)

    db = get_db()
    for i, it in enumerate(items):
        db.execute("UPDATE wbs_item SET sort_order = ? WHERE id = ?", (i, it['id']))
    db.commit()

    recalculate_codes(project_id)

    return {
        'moved_id': moved['id'],
        'task_name': moved.get('task_name', ''),
        'source_row': source_row,
        'target_row': target_row,
        'position': pos,
        'new_row': new_idx + 1,
    }


def process_command(project_id: int, user_input: str) -> dict:
    """자연어 입력을 파싱하고 실행하여 결과를 반환한다."""
    project_overview = _get_project_overview(project_id)
    if current_app.config.get('AI_MODEL') == 'GEMMA':
        # 작은 컨텍스트 모델 — 전체 행 대신 압축 요약 + 축약 프롬프트 사용
        items_summary = _get_compact_summary(project_id)
        system_prompt = _build_compact_system_prompt(items_summary, project_overview[:800])
    else:
        items_summary = _get_items_summary(project_id)
        system_prompt = _build_system_prompt(items_summary, project_overview=project_overview)
    user_prompt = f'질의: "{user_input}"\nJSON 형식으로만 응답하세요. 코드블록으로 감싸지 마세요.'

    try:
        response_text = _call_llm(system_prompt, user_prompt)
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

        elif action == 'move':
            result = _execute_move(
                project_id,
                parsed.get('source_row', 0),
                parsed.get('target_row', 0),
                parsed.get('position', 'above'),
            )
            if 'error' in result:
                return {'success': False, 'message': result['error']}
            return {
                'success': True,
                'action': 'move',
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

"""WBS AI Assistant — LLM을 활용한 자연어 명령 처리

자연어 입력을 파싱하여 WBS 데이터 조회/추가/삭제 명령으로 변환하고 실행한다.
template/claude_query_parser.py의 패턴을 참고하여 구현.
"""
import json
import logging
import subprocess
import sys
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

# CLAUDE(AI_MODEL=CLAUDE)에서 AI_MODEL_NAME 미설정 시 사용할 기본 모델
_CLAUDE_DEFAULT_MODEL = "claude-opus-5"

# 분석 대상 기간(일). 프롬프트에 실을 태스크를 오늘~4주로 제한해 입력 토큰을 억제한다.
_ANALYSIS_WINDOW_DAYS = 28

# generate 액션 고정값 — 담당자/공수/진행률은 LLM이 아니라 서버가 정한다
_GENERATED_ASSIGNEE = 'AI생성'
_GENERATED_EFFORT = 2
_GENERATE_MAX_ITEMS = 30


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """AI_MODEL 설정에 따라 LLM을 호출한다.

    GEMINI → OpenAI 호환 엔드포인트, CLAUDE → Anthropic Messages API,
    LOCAL → claude -p CLI.
    """
    provider = current_app.config.get("AI_MODEL", "LOCAL")
    if provider == "GEMINI":
        return _call_openai_compatible(system_prompt, user_prompt)
    if provider == "CLAUDE":
        return _call_anthropic(system_prompt, user_prompt)
    return _call_claude_cli(system_prompt, user_prompt)


def _call_openai_compatible(system_prompt: str, user_prompt: str) -> str:
    """OpenAI 호환 엔드포인트(Gemini)를 호출한다."""
    from openai import OpenAI

    cfg = current_app.config
    base_url = cfg.get("AI_BASE_URL") or _GEMINI_DEFAULT_BASE_URL
    # 추론(thinking) 모델은 "생각" 토큰까지 소비하므로 답(JSON)을 낼 여유가 필요하다.
    max_tokens = 2048
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


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Anthropic Messages API를 호출한다 (AI_MODEL=CLAUDE).

    Claude 4.7 이후 모델은 temperature/top_p 를 받지 않으므로(400) 추론 깊이는
    output_config.effort 로 조절한다. 자연어→JSON 변환은 짧고 지연에 민감한
    작업이라 medium 사용. thinking 은 기본 ON이며 max_tokens 를 함께 소비한다.
    """
    from anthropic import Anthropic

    cfg = current_app.config
    try:
        client = Anthropic(api_key=cfg["AI_API_KEY"])
        resp = client.messages.create(
            model=cfg.get("AI_MODEL_NAME") or _CLAUDE_DEFAULT_MODEL,
            max_tokens=16000,
            system=system_prompt,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("Claude가 안전 정책에 따라 요청을 거부했습니다")
        output = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not output:
            raise RuntimeError(f"LLM이 빈 응답을 반환했습니다 (stop_reason={resp.stop_reason})")
        return output
    except Exception as e:
        raise RuntimeError(f"LLM 호출 오류(CLAUDE): {e}")


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
- category: 구분 (작업 성격 분류 — 아래 "그리드 계층 구조" 참고)
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

## 그리드 계층 구조 (구분 > Task > 서브태스크 > 세부항목)
- **구분(category)** — 작업의 성격 분류. 아래 표준 값 중에서 고른다
- **Task(task_name)** — 대표 작업. 기능/모듈 단위의 큰 묶음 (예: "주문 관리", "실시간 협업")
- **서브태스크(subtask)** — 그 대표 작업에 속한 개별 작업 단위 (예: "API 구현", "SSE 브로커")
- **세부항목(detail)** — 해당 서브태스크에서 실제로 무엇을 하는지 적는 설명. 서브태스크의 상세 내용이다

예) [개발] 주문 관리 / API 구현 / 주문 생성·취소 엔드포인트 구현

### 구분(category) 표준 값
기획 · 설계 · 개발 · 개발/관리 · 테스트 · 운영 · 인프라 · 보안 · 배포

### 구분 추론 규칙
사용자가 구분을 직접 말하지 않아도 **Task·서브태스크·세부항목의 내용에서 유추해 반드시 채운다** (빈 값 금지).
- 요구사항 수집, 범위·일정 정의 → 기획
- 화면/DB/API 설계, ERD, 명세서, 아키텍처 → 설계
- 기능 구현, 코딩, 리팩터링, 마이그레이션 스크립트 → 개발
- 일정·이슈·산출물 관리, 회의, 보고, 리뷰 → 개발/관리
- 단위/통합/인수 테스트, QA, 시나리오 검증, 버그 수정 검증 → 테스트
- 장애 대응, 모니터링, 운영 이관, 사용자 지원 → 운영
- 서버·네트워크·DB 구축, CI 환경, 리소스 증설 → 인프라
- 취약점 점검, 인증·권한, 암호화, 보안 심사 → 보안
- 릴리스, 배포 자동화, 롤백, 형상 관리 → 배포

예) "테스트 태스크 만들어줘" → category="테스트", "결제 API 만들어줘" → category="개발".
표준 값으로 분류가 애매하면 가장 가까운 값을 고르고, 아래 WBS 데이터에 이미 쓰이고 있는
구분 값이 있으면 **새 값을 만들지 말고 그 값을 재사용**한다.

## 현재 WBS 데이터 요약
※ 아래 목록은 **전체가 아니라 분석 대상(미완료 + 지연·향후 4주)** 만 담고 있습니다.
   완료 항목과 4주 밖 미래 항목은 헤더 집계에만 반영됩니다. 목록에 없는 항목도
   query의 filters로 조회할 수 있으니, 요약에 없다는 이유로 "없다"고 단정하지 마세요.
{items_summary}

## 명령 타입
1. **query** — 조건에 맞는 항목 조회/필터링
2. **add** — 새 항목 추가
3. **delete** — 항목 삭제
4. **update** — 항목 수정
5. **move** — 행 순서 이동 (TID/행 번호 기준)
6. **generate** — 프로젝트 개요/마일스톤을 근거로 태스크 여러 건 일괄 생성

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

### generate 타입 예시 (마일스톤 기반 태스크 일괄 생성):
{{
    "action": "generate",
    "items": [
        {{"category": "설계", "task_name": "DB 설계", "subtask": "ERD 작성", "detail": "주문/결제 테이블 정의"}},
        {{"category": "개발", "task_name": "주문 관리", "subtask": "API 구현", "detail": "주문 생성·취소 엔드포인트"}}
    ],
    "description": "마일스톤 M1 기준으로 2건을 생성했습니다."
}}

### generate 타입 예시 2 — 기존 Task가 있어 세부항목을 추가하는 경우:
현재 WBS에 `[개발] 실시간 협업 / SSE 브로커` 항목이 이미 있을 때, 같은 구분·Task·서브태스크를
**그대로 복사**하고 detail 만 새로 쓴다 (네 필드 모두 반드시 채운다):
{{
    "action": "generate",
    "items": [
        {{"category": "개발", "task_name": "실시간 협업", "subtask": "SSE 브로커",
          "detail": "Redis 장애 시 인메모리 폴백 전환 처리", "plan_start": "2026-08-24", "plan_end": "2026-08-25"}}
    ],
    "description": "SSE 브로커 세부항목 1건을 추가했습니다."
}}
※ category 에 마일스톤명("실시간 협업 안정화")을 넣거나 task_name 을 빈 값으로 두는 것은 **오류**다.
   category=작업 성격(개발), task_name=기능/모듈(실시간 협업), subtask=작업 단위(SSE 브로커).

※ generate 규칙:
- "마일스톤 기준으로 태스크 만들어줘", "WBS 초안 작성해줘" 같은 **생성 요청**에 사용 (단건 추가는 add)
- 위 **프로젝트 개요**에 PM이 기입한 목적·마일스톤을 근거로 작성한다. 개요가 비어 있으면
  생성하지 말고 query로 응답하며 description에 개요 기입이 필요하다고 안내한다
- **기존 Task가 있으면** 위 WBS 데이터의 `구분`/`Task`/`서브태스크` 값을 그대로 재사용하고
  새로운 **세부항목(detail)** 을 채운다. 유사한 구분/Task를 새로 만들지 말 것
- 기존 Task가 없으면 마일스톤 단위로 구분/Task/서브태스크/세부항목을 새로 구성한다
- **네 필드는 위 "그리드 계층 구조"를 그대로 따른다**: 구분=작업 성격(표준 값에서 선택),
  Task=기능/모듈 단위, 서브태스크=그 안의 작업 단위, 세부항목=서브태스크의 상세 설명.
  구분은 사용자가 말하지 않아도 **생성할 작업 내용에서 추론해 채우고**, 위 WBS 데이터에
  이미 쓰인 구분 값이 있으면 그것을 재사용한다. **마일스톤명이나 Task명을 구분에 넣지 말 것**
- 같은 요청 안에서 성격이 다른 작업이 섞이면 항목별로 구분을 다르게 넣는다
  (예: "결제 기능 만들고 테스트까지" → 구현 항목은 개발, 검증 항목은 테스트)
- **담당자·공수·진행률은 넣지 말 것** — 서버가 '{_GENERATED_ASSIGNEE}' / {_GENERATED_EFFORT} / 0 으로 고정한다
- **일정**: 프로젝트 개요의 마일스톤이나 사용자 질의에 **시기가 적혀 있으면 그에 맞춰**
  plan_start/plan_end를 YYYY-MM-DD로 넣는다. "8월 3주" 같은 표현은 해당 주의 평일 범위로
  환산한다(오늘이 {today}일 때 "8월 3주" → 2026-08-17~2026-08-21 사이). 토·일은 배정 금지.
  마일스톤별로 일정이 다르면 항목별로 다르게 넣어야 하며, **전 항목을 같은 날짜로 몰지 말 것**.
  어디에도 시기 언급이 없을 때만 생략한다 (생략 시 서버가 오늘 기준 영업일로 채움)
- **중복 금지**: 위 WBS 데이터에 이미 있는 (구분·Task·서브태스크·세부항목) 조합은 다시 만들지 않는다.
  기존 구분/Task/서브태스크 체계는 따르되 세부항목은 **기존에 없는 새로운 작업 단위**로 작성한다.
  기존 항목의 내용을 고치려는 것이면 generate 가 아니라 update 를 사용한다
- 한 번에 최대 {_GENERATE_MAX_ITEMS}건

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


def _parse_date(value) -> "date | None":
    """'YYYY-MM-DD' 문자열을 date로 파싱한다. 실패 시 None."""
    s = (value or '').strip()
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _get_items_summary(project_id: int) -> str:
    """분석용 WBS 요약을 반환한다 (미완료 + 지연·향후 4주 항목만).

    전체 행을 나열하면 입력 토큰이 프로젝트 규모에 비례해 커지므로 대상을 좁힌다:
    ① 완료(진행률 100) 제외 — 분석 기준은 남아 있는 태스크다.
    ② 계획기간이 오늘~4주 창을 벗어난 미래 항목 제외 — 현 시점 의사결정과 무관.
    단, 기한이 지난 미완료(지연)는 창 밖이어도 분석의 핵심이라 포함한다.

    전체 건수·완료 수는 헤더 집계로 남겨 LLM이 전반 맥락을 잃지 않게 하고,
    LLM이 만든 query 필터는 `_execute_query`가 전체 데이터로 실행하므로 조회
    결과 정확도에는 영향이 없다 (이 요약은 insight 근거·필터 생성용).
    """
    items = wbs_model.get_flat_items(project_id)
    if not items:
        return "항목 없음"

    total = len(items)
    done = sum(1 for it in items if (it.get('progress') or 0) >= 100)
    in_prog = sum(1 for it in items if 0 < (it.get('progress') or 0) < 100)
    not_started = total - done - in_prog
    avg_progress = round(sum(it.get('progress') or 0 for it in items) / total)

    # 프로젝트가 실제로 쓰고 있는 구분 값 — 생성 시 새 값을 만들지 않고 재사용하게 하는 근거.
    # 완료·미래 항목까지 포함해 집계한다(아래 목록에서 걸러지더라도 어휘는 유효하므로).
    used_categories = []
    for it in items:
        c = (it.get('category') or '').strip()
        if c and c not in used_categories:
            used_categories.append(c)
    cat_line = ("현재 사용 중인 구분: " + ", ".join(used_categories)) if used_categories \
        else "현재 사용 중인 구분: (없음 — 표준 값에서 추론해 채울 것)"

    today = date.today()
    window_end = today + timedelta(days=_ANALYSIS_WINDOW_DAYS)

    lines = []
    skipped_future = 0
    for i, item in enumerate(items):
        row_num = i + 1   # TID는 전체 flat 순번(그리드 표시)과 일치해야 한다
        if (item.get('progress') or 0) >= 100:
            continue

        sched = _compute_schedule_info(item)
        ps = _parse_date(item.get('plan_start'))
        pe = _parse_date(item.get('plan_end'))
        s, e = (ps or pe), (pe or ps)
        # 계획기간이 오늘~창끝과 겹치면 대상. 일자 미기입은 판단 불가라 포함.
        in_window = s is None or (s <= window_end and e >= today)
        if not (in_window or sched['has_end_delay']):
            skipped_future += 1
            continue

        cat = item.get('category', '') or '-'
        name = item.get('task_name', '') or ''
        sub = item.get('subtask', '') or ''
        assignee = item.get('assignee', '') or ''
        progress = item.get('progress', 0) or 0
        plan_end = item.get('plan_end', '') or ''
        detail = (item.get('detail', '') or '')[:30]
        gap_info = ''
        if sched['end_gap_days'] is not None and sched['end_gap_days'] != 0:
            gap_info = f" 종료갭:{sched['end_gap_days']:+d}일"
        status = (item.get('status', '') or '')[:40]
        lines.append(
            f"  {row_num}. [{cat}] {name} / 서브:{sub} 담당:{assignee} "
            f"진행:{progress}% 계획완료:{plan_end}{gap_info} 상태:{status} 세부:{detail}"
        )

    body = "\n".join(lines) if lines else "  (해당 없음)"
    return (
        f"총 {total}건 (완료 {done} / 진행중 {in_prog} / 미착수 {not_started}, 평균진행률 {avg_progress}%)\n"
        f"{cat_line}\n"
        f"아래는 **미완료 중 지연 또는 계획기간이 {today}~{window_end}(4주)와 겹치는 {len(lines)}건**입니다:\n"
        f"{body}\n"
        f"※ 완료 {done}건 / 4주 창 밖 미래 {skipped_future}건은 목록에서 생략됨 "
        f"(질의 시 filters로 전체 조회 가능)"
    )


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


def _next_business_day(d: "date") -> "date":
    """주말이면 다음 월요일로 밀어준다 (5=토, 6=일)."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _add_business_days(d: "date", days: int) -> "date":
    """d 로부터 영업일 days 일 뒤 날짜를 반환한다 (주말 건너뜀)."""
    cur = _next_business_day(d)
    for _ in range(days):
        cur = _next_business_day(cur + timedelta(days=1))
    return cur


def _execute_generate(project_id: int, items: list) -> dict:
    """마일스톤 기반 태스크를 일괄 생성한다.

    담당자·공수·진행률은 서버가 고정하고(LLM 값 무시), 일정을 지정하지 않은 항목은
    오늘(주말이면 다음 영업일)부터 공수만큼의 영업일로 계획일자를 채운다.
    구분·Task·서브태스크·세부항목이 모두 같은 기존 항목은 건너뛴다(LLM 중복 생성 방어).
    """
    if not isinstance(items, list) or not items:
        return {'error': '생성할 항목이 없습니다.'}

    plan_start = _next_business_day(date.today())
    plan_end = _add_business_days(plan_start, _GENERATED_EFFORT - 1)

    def _key(d):
        return tuple((d.get(k) or '').strip() for k in ('category', 'task_name', 'subtask', 'detail'))

    seen = {_key(it) for it in wbs_model.get_flat_items(project_id)}

    created, skipped, invalid = [], 0, 0
    for raw in items[:_GENERATE_MAX_ITEMS]:
        if not isinstance(raw, dict):
            invalid += 1
            continue
        key = _key(raw)
        # Task명·세부항목이 없으면 그리드에서 식별 불가한 행이 된다.
        # (LLM이 category 자리에 마일스톤명을 넣고 task_name을 비우는 실수를 하므로 방어)
        if not (raw.get('task_name') or '').strip() or not (raw.get('detail') or '').strip():
            invalid += 1
            continue
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        created.append(wbs_service.create_item({
            'project_id': project_id,
            'category': raw.get('category', ''),
            'task_name': raw.get('task_name', ''),
            'subtask': raw.get('subtask', ''),
            'detail': raw.get('detail', ''),
            'plan_start': (raw.get('plan_start') or '').strip() or str(plan_start),
            'plan_end': (raw.get('plan_end') or '').strip() or str(plan_end),
            'assignee': _GENERATED_ASSIGNEE,
            'effort': _GENERATED_EFFORT,
            'progress': 0,
        }))

    if not created:
        if skipped:
            return {'error': '이미 등록된 항목이라 새로 만들 것이 없습니다.'}
        if invalid:
            return {'error': 'Task명·세부항목이 비어 생성하지 못했습니다. 다시 시도해주세요.'}
        return {'error': '생성할 항목이 없습니다.'}
    return {'items': created, 'count': len(created), 'skipped': skipped + invalid}


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

        elif action == 'generate':
            result = _execute_generate(project_id, parsed.get('items', []))
            if 'error' in result:
                return {'success': False, 'message': result['error']}
            return {
                'success': True,
                'action': 'generate',
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

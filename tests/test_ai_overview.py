"""AI 어시스턴트가 프로젝트 개요(description)를 프롬프트에 주입하는지 검증."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from app.services import ai_assistant


def test_get_project_overview_includes_description(app, admin_client):
    resp = admin_client.post('/api/projects', json={
        'name': '개요 테스트',
        'description': '[목적] X\n[마일스톤] M1 4/30 / M2 5/31',
        'start_date': '2026-04-01',
        'end_date': '2026-06-30',
    })
    pid = resp.get_json()['id']

    with app.app_context():
        overview = ai_assistant._get_project_overview(pid)

    assert '개요 테스트' in overview
    assert '2026-04-01' in overview and '2026-06-30' in overview
    assert '[목적] X' in overview
    assert 'M1 4/30' in overview


def test_get_project_overview_empty_description(app, admin_client):
    pid = admin_client.post('/api/projects', json={'name': '빈설명'}).get_json()['id']
    with app.app_context():
        overview = ai_assistant._get_project_overview(pid)
    assert '빈설명' in overview
    assert '미기입' in overview


def test_build_system_prompt_injects_overview():
    prompt = ai_assistant._build_system_prompt(
        items_summary="총 0건",
        project_overview="- 프로젝트명: Demo\n- 기간: 2026-01-01 ~ 2026-12-31",
    )
    assert '## 프로젝트 개요' in prompt
    assert 'Demo' in prompt
    assert '프로젝트 분석' in prompt  # 전반 분석 가이드 지침이 들어있어야 함


def test_build_system_prompt_without_overview_marks_empty():
    prompt = ai_assistant._build_system_prompt(items_summary="총 0건")
    assert '(프로젝트 개요 미기입)' in prompt


def test_build_system_prompt_explains_hierarchy_and_category():
    """구분>Task>서브태스크>세부항목 계층과 구분 추론 규칙이 프롬프트에 있어야 한다."""
    prompt = ai_assistant._build_system_prompt(items_summary="총 0건")
    assert '구분 > Task > 서브태스크 > 세부항목' in prompt
    assert '구분 추론 규칙' in prompt
    for cat in ('기획', '설계', '개발/관리', '테스트', '운영', '인프라', '보안', '배포'):
        assert cat in prompt


def test_process_command_passes_overview_to_prompt(app, admin_client, monkeypatch):
    """process_command 호출 시 _call_llm 로 전달되는 system prompt에
    프로젝트 description 이 포함되는지 확인."""
    pid = admin_client.post('/api/projects', json={
        'name': 'FeedTest',
        'description': '[마일스톤] M1 4/30 기본 CRUD 완성',
    }).get_json()['id']

    captured = {}

    def _fake_call(system_prompt, user_prompt):
        captured['system'] = system_prompt
        captured['user'] = user_prompt
        return '{"action": "query", "filters": {}, "description": "ok", "insight": "i"}'

    monkeypatch.setattr(ai_assistant, '_call_llm', _fake_call)

    with app.app_context():
        result = ai_assistant.process_command(pid, '프로젝트 전반적인 진척상황 분석해줘')

    assert result['success'] is True
    assert '[마일스톤] M1 4/30 기본 CRUD 완성' in captured['system']
    assert 'FeedTest' in captured['system']
    # 질의 자체는 user prompt 로 전달
    assert '프로젝트 전반적인 진척상황' in captured['user']


def test_items_summary_scopes_to_open_tasks_in_window(app, admin_client):
    """요약 대상: 완료 제외 / 4주 창 밖 미래 제외 / 지연은 창 밖이어도 포함."""
    pid = admin_client.post('/api/projects', json={'name': 'WindowTest'}).get_json()['id']
    today = date.today()

    def _add(**kw):
        admin_client.post(f'/api/wbs/{pid}/items', json=kw)

    # 이번 주 진행중 → 포함
    _add(task_name='WK', subtask='금주작업', assignee='가나',
         plan_start=str(today), plan_end=str(today + timedelta(days=3)), progress=30)
    # 완료 → 제외
    _add(task_name='DONE', subtask='완료작업', assignee='다라',
         plan_start=str(today), plan_end=str(today + timedelta(days=1)), progress=100)
    # 기한 경과 미완료(지연) → 창 밖(과거)이지만 포함
    _add(task_name='LATE', subtask='지연작업', assignee='마바',
         plan_start=str(today - timedelta(days=40)), plan_end=str(today - timedelta(days=30)), progress=50)
    # 4주 창 밖 미래 → 제외
    _add(task_name='FUTURE', subtask='미래작업', assignee='사아',
         plan_start=str(today + timedelta(days=60)), plan_end=str(today + timedelta(days=70)), progress=0)

    with app.app_context():
        summary = ai_assistant._get_items_summary(pid)

    assert '금주작업' in summary
    assert '지연작업' in summary
    assert '완료작업' not in summary
    assert '미래작업' not in summary
    # 전체 맥락은 헤더 집계로 유지
    assert '총 4건' in summary and '완료 1' in summary


def test_items_summary_exposes_categories(app, admin_client):
    """요약에 각 행의 구분과 '현재 사용 중인 구분' 목록이 실려야 한다."""
    pid = admin_client.post('/api/projects', json={'name': 'CatTest'}).get_json()['id']
    today = date.today()
    admin_client.post(f'/api/wbs/{pid}/items', json={
        'category': '테스트', 'task_name': '결제', 'subtask': '통합테스트',
        'plan_start': str(today), 'plan_end': str(today + timedelta(days=2)), 'progress': 10,
    })

    with app.app_context():
        summary = ai_assistant._get_items_summary(pid)

    assert '현재 사용 중인 구분: 테스트' in summary
    assert '[테스트] 결제 / 서브:통합테스트' in summary


def test_execute_generate_fills_server_defaults(app, admin_client):
    """generate: 담당자/공수/진행률 고정 + 일정 미지정 시 오늘 기준 영업일."""
    pid = admin_client.post('/api/projects', json={'name': 'GenTest'}).get_json()['id']

    with app.app_context():
        result = ai_assistant._execute_generate(pid, [
            {'category': '설계', 'task_name': 'DB 설계', 'subtask': 'ERD 작성', 'detail': '주문 테이블 정의'},
            # LLM이 담당자·공수를 넣어도 서버 값으로 덮어써야 한다
            {'category': '개발', 'task_name': 'API', 'subtask': '구현', 'detail': '주문 생성',
             'assignee': '아무개', 'effort': 99, 'progress': 50},
        ])

    assert result['count'] == 2
    expected_start = ai_assistant._next_business_day(date.today())
    expected_end = ai_assistant._add_business_days(expected_start, 1)
    for item in result['items']:
        assert item['assignee'] == 'AI생성'
        assert item['effort'] == 2
        assert item['progress'] == 0
        assert item['plan_start'] == str(expected_start)
        assert item['plan_end'] == str(expected_end)
    assert result['items'][0]['detail'] == '주문 테이블 정의'


def test_execute_generate_keeps_explicit_dates_and_skips_invalid(app, admin_client):
    """Task명 또는 세부항목이 비면 생성하지 않는다 (LLM 필드 밀림 방어)."""
    pid = admin_client.post('/api/projects', json={'name': 'GenTest2'}).get_json()['id']

    with app.app_context():
        result = ai_assistant._execute_generate(pid, [
            {'category': '기획', 'task_name': '요구사항', 'subtask': '인터뷰', 'detail': '부서별 인터뷰',
             'plan_start': '2026-09-01', 'plan_end': '2026-09-04'},
            # category 자리에 마일스톤명이 오고 task_name 이 빈 실제 관측 사례
            {'category': '실시간 협업 안정화', 'task_name': '', 'subtask': 'SSE 브로커', 'detail': '스키마 정의'},
            {'category': '개발', 'task_name': 'API', 'subtask': '구현', 'detail': ''},  # 세부항목 없음
            'not-a-dict',
        ])

    assert result['count'] == 1
    assert result['skipped'] == 3
    assert result['items'][0]['plan_start'] == '2026-09-01'
    assert result['items'][0]['plan_end'] == '2026-09-04'


def test_execute_generate_skips_duplicates(app, admin_client):
    """구분·Task·서브태스크·세부항목이 모두 같은 기존 항목은 다시 만들지 않는다."""
    pid = admin_client.post('/api/projects', json={'name': 'DupTest'}).get_json()['id']
    dup = {'category': '설계', 'task_name': 'DB 설계', 'subtask': 'ERD 작성', 'detail': '테이블 정의'}
    admin_client.post(f'/api/wbs/{pid}/items', json=dup)

    with app.app_context():
        result = ai_assistant._execute_generate(pid, [
            dict(dup),                                    # 기존과 완전 동일 → 스킵
            dict(dup, detail='인덱스 설계'),               # 세부항목만 다름 → 생성
            dict(dup, detail='인덱스 설계'),               # 같은 응답 내 중복 → 스킵
        ])

    assert result['count'] == 1
    assert result['skipped'] == 2
    assert result['items'][0]['detail'] == '인덱스 설계'

    # 전부 중복이면 오류 메시지로 안내
    with app.app_context():
        again = ai_assistant._execute_generate(pid, [dict(dup)])
    assert '이미 등록된' in again['error']


def test_execute_generate_rejects_empty_list(app, admin_client):
    pid = admin_client.post('/api/projects', json={'name': 'GenTest3'}).get_json()['id']
    with app.app_context():
        assert 'error' in ai_assistant._execute_generate(pid, [])


def test_business_day_helpers_skip_weekend():
    # 2026-08-08 은 토요일 → 다음 영업일은 월요일 08-10
    assert ai_assistant._next_business_day(date(2026, 8, 8)) == date(2026, 8, 10)
    assert ai_assistant._next_business_day(date(2026, 8, 10)) == date(2026, 8, 10)
    # 금요일 + 1영업일 = 다음 주 월요일
    assert ai_assistant._add_business_days(date(2026, 8, 7), 1) == date(2026, 8, 10)


def test_process_command_generate_creates_items(app, admin_client, monkeypatch):
    """generate 액션 종단: LLM 응답 → 항목 생성 → 그리드 조회로 확인."""
    pid = admin_client.post('/api/projects', json={
        'name': 'GenFlow', 'description': '[마일스톤] M1 설계완료',
    }).get_json()['id']

    monkeypatch.setattr(ai_assistant, '_call_llm', lambda s, u: json.dumps({
        'action': 'generate',
        'items': [{'category': '설계', 'task_name': 'DB 설계', 'subtask': 'ERD 작성', 'detail': '테이블 정의'}],
        'description': 'M1 기준 1건 생성',
    }, ensure_ascii=False))

    with app.app_context():
        result = ai_assistant.process_command(pid, '마일스톤 기준으로 태스크 만들어줘')

    assert result['success'] is True
    assert result['action'] == 'generate'
    assert result['data']['count'] == 1

    items = admin_client.get(f'/api/wbs/{pid}/items?mode=flat').get_json()
    assert len(items) == 1
    assert items[0]['assignee'] == 'AI생성'
    assert items[0]['detail'] == '테이블 정의'


def test_call_llm_dispatches_by_ai_model(app, monkeypatch):
    """AI_MODEL 설정에 따라 OpenAI 호환/Anthropic/CLI 경로로 라우팅되는지 검증."""
    calls = []
    monkeypatch.setattr(ai_assistant, '_call_openai_compatible',
                        lambda s, u: calls.append('openai') or 'openai')
    monkeypatch.setattr(ai_assistant, '_call_anthropic',
                        lambda s, u: calls.append('anthropic') or 'anthropic')
    monkeypatch.setattr(ai_assistant, '_call_claude_cli',
                        lambda s, u: calls.append('cli') or 'cli')

    for model, expected in (('GEMINI', 'openai'), ('CLAUDE', 'anthropic'), ('LOCAL', 'cli')):
        calls.clear()
        with app.app_context():
            app.config['AI_MODEL'] = model
            assert ai_assistant._call_llm('sys', 'user') == expected
        assert calls == [expected]


class _FakeTextBlock:
    type = 'text'

    def __init__(self, text):
        self.text = text


def _fake_anthropic(monkeypatch, captured, blocks, stop_reason='end_turn'):
    """anthropic.Anthropic 을 가짜 클라이언트로 교체한다 (요청 인자 캡처용)."""
    class _Resp:
        pass

    resp = _Resp()
    resp.stop_reason = stop_reason
    resp.content = blocks

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return resp

    class _FakeClient:
        def __init__(self, **kwargs):
            captured['api_key'] = kwargs.get('api_key')
            self.messages = _Messages()

    monkeypatch.setattr('anthropic.Anthropic', _FakeClient)


def test_call_anthropic_request_shape(app, monkeypatch):
    """CLAUDE 경로: 기본 모델·system·effort 전달, temperature 미전달(4.7+ 는 400)."""
    captured = {}
    _fake_anthropic(monkeypatch, captured, [_FakeTextBlock('{"action": "query"}')])

    with app.app_context():
        app.config['AI_API_KEY'] = 'sk-test'
        app.config['AI_MODEL_NAME'] = ''
        out = ai_assistant._call_anthropic('sys', 'user')

    assert out == '{"action": "query"}'
    assert captured['api_key'] == 'sk-test'
    assert captured['model'] == 'claude-opus-5'   # AI_MODEL_NAME 미설정 시 기본값
    assert captured['system'] == 'sys'
    assert captured['messages'] == [{'role': 'user', 'content': 'user'}]
    assert captured['output_config'] == {'effort': 'medium'}
    assert 'temperature' not in captured
    assert 'top_p' not in captured


def test_call_anthropic_uses_configured_model(app, monkeypatch):
    captured = {}
    _fake_anthropic(monkeypatch, captured, [_FakeTextBlock('{}')])

    with app.app_context():
        app.config['AI_API_KEY'] = 'sk-test'
        app.config['AI_MODEL_NAME'] = 'claude-sonnet-5'
        ai_assistant._call_anthropic('sys', 'user')

    assert captured['model'] == 'claude-sonnet-5'


def test_call_anthropic_raises_on_refusal(app, monkeypatch):
    """stop_reason=refusal 은 content 를 읽지 않고 오류로 변환."""
    captured = {}
    _fake_anthropic(monkeypatch, captured, [], stop_reason='refusal')

    with app.app_context():
        app.config['AI_API_KEY'] = 'sk-test'
        with pytest.raises(RuntimeError, match='거부'):
            ai_assistant._call_anthropic('sys', 'user')


def test_call_anthropic_raises_on_empty_output(app, monkeypatch):
    captured = {}
    _fake_anthropic(monkeypatch, captured, [_FakeTextBlock('   ')])

    with app.app_context():
        app.config['AI_API_KEY'] = 'sk-test'
        with pytest.raises(RuntimeError, match='빈 응답'):
            ai_assistant._call_anthropic('sys', 'user')

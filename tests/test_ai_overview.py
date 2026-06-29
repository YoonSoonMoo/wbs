"""AI 어시스턴트가 프로젝트 개요(description)를 프롬프트에 주입하는지 검증."""
from __future__ import annotations

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


def test_gemma_uses_compact_prompt(app, admin_client, monkeypatch):
    """AI_MODEL=GEMMA 시 전체 행 나열 대신 압축 요약 프롬프트가 사용되는지 검증."""
    pid = admin_client.post('/api/projects', json={'name': 'CompactTest'}).get_json()['id']
    admin_client.post(f'/api/wbs/{pid}/items', json={
        'task_name': 'T1', 'assignee': '홍길동', 'progress': 100,
    })

    captured = {}

    def _fake_call(system_prompt, user_prompt):
        captured['system'] = system_prompt
        return '{"action": "query", "filters": {}, "description": "ok"}'

    monkeypatch.setattr(ai_assistant, '_call_llm', _fake_call)

    with app.app_context():
        app.config['AI_MODEL'] = 'GEMMA'
        result = ai_assistant.process_command(pid, '전체 현황 알려줘')

    assert result['success'] is True
    # 압축 프롬프트 표식 + 집계 라인 포함, 행 단위 상세 나열은 없음
    assert 'WBS 현황 요약' in captured['system']
    assert '담당자별 건수' in captured['system']
    assert '세부:' not in captured['system']  # 전체 나열(_get_items_summary) 표식 부재


def test_call_llm_dispatches_by_ai_model(app, monkeypatch):
    """AI_MODEL 설정에 따라 OpenAI 호환/CLI 경로로 라우팅되는지 검증."""
    calls = []
    monkeypatch.setattr(ai_assistant, '_call_openai_compatible',
                        lambda s, u: calls.append('openai') or 'openai')
    monkeypatch.setattr(ai_assistant, '_call_claude_cli',
                        lambda s, u: calls.append('cli') or 'cli')

    for model, expected in (('GEMINI', 'openai'), ('GEMMA', 'openai'), ('LOCAL', 'cli')):
        calls.clear()
        with app.app_context():
            app.config['AI_MODEL'] = model
            assert ai_assistant._call_llm('sys', 'user') == expected
        assert calls == [expected]

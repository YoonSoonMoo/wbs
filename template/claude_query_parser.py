"""Claude Code CLI를 활용한 쿼리 파서 및 AI 요약기

GeminiQueryParser와 동일한 인터페이스를 제공하며,
로컬 Claude Code CLI(claude -p)를 subprocess로 호출합니다.
"""
import os
import sys
import json
import subprocess
import tempfile
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional


class ClaudeQueryParser:
    def __init__(self):
        # claude CLI 사용 가능 여부 확인 (Windows에서는 shell=True 필요)
        self._is_windows = sys.platform == "win32"
        try:
            result = subprocess.run(
                "claude --version",
                capture_output=True, text=True, timeout=10,
                shell=self._is_windows
            )
            if result.returncode != 0:
                raise RuntimeError("claude CLI를 실행할 수 없습니다")
            logging.info(f"Claude CLI 확인됨: {result.stdout.strip()}")
        except FileNotFoundError:
            raise RuntimeError("claude CLI가 설치되어 있지 않습니다. Claude Code를 먼저 설치하세요.")

        # JIRA 메타데이터 (GeminiQueryParser와 동일)
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        return {
            "projects": ["FULFILMENT", "SABANGNET", "NSMSCOMMON", "NPPURIO", "NBIZPPURIO", "XIPROJ", "NGW"],
            "statuses": ["Open", "진행", "완료", "TC/검수", "보류", "Confirmed", "Done"],
            "priorities": ["Critical", "Major", "Minor", "Trivial"],
            "issue_types": ["기능개선", "개발요청", "운영요청", "버그", "Task"],
            "custom_fields": {
                "cf[12291]": "담당자(현업)",
                "cf[12300]": "진척률"
            },
            "common_queries": {
                "이번 주": "created >= startOfWeek()",
                "지난 주": "created >= startOfWeek(-1) AND created < startOfWeek()",
                "이번 달": "created >= startOfMonth()",
                "최근 7일": "created >= -7d",
                "최근 30일": "created >= -30d",
                "미완료": "status not in (완료, Confirmed, Done)",
                "완료": "status in (완료, Confirmed, Done)",
                "진행중": "status = 진행",
                "지연": "duedate < now() AND status not in (완료, Confirmed, Done)"
            }
        }

    def _call_claude(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Claude Code CLI를 subprocess로 호출 (긴 프롬프트는 stdin으로 전달)"""
        full_prompt = f"""[시스템 지시사항]
{system_prompt}

[사용자 요청]
{user_prompt}"""

        try:
            result = subprocess.run(
                "claude -p --max-turns 1",
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                shell=self._is_windows
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "알 수 없는 오류"
                raise RuntimeError(f"claude CLI 오류 (code={result.returncode}): {error_msg}")

            output = result.stdout.strip()
            if not output:
                raise RuntimeError("claude CLI가 빈 응답을 반환했습니다")

            return output

        except subprocess.TimeoutExpired:
            raise RuntimeError("claude CLI 호출 타임아웃 (120초)")

    def parse_query(self, natural_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """자연어 질의를 JQL로 변환"""
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(natural_query, context)

        try:
            response_text = self._call_claude(system_prompt, user_prompt)
            parsed = self._parse_json_response(response_text)

            if not self._validate_jql(parsed.get('jql', '')):
                logging.warning(f"생성된 JQL이 유효하지 않을 수 있습니다: {parsed.get('jql')}")

            logging.info(f"자연어 질의: '{natural_query}' → JQL: '{parsed.get('jql')}'")
            return parsed

        except Exception as e:
            logging.error(f"쿼리 파싱 실패: {e}", exc_info=True)
            raise

    def summarize_content(self, content: str) -> str:
        """업무 내용을 요약합니다."""
        if not content or not content.strip():
            return "내용 없음"

        system_prompt = "당신은 텍스트 요약 전문가입니다. 핵심 내용만 추출하여 300자 이내로 요약하세요."
        user_prompt = f"다음 업무 내용을 요약해주세요:\n\n{content}"

        try:
            return self._call_claude(system_prompt, user_prompt).strip()
        except Exception as e:
            logging.error(f"내용 요약 실패: {e}")
            return content[:300] + "..." if len(content) > 300 else content

    def summarize_progress(self, history_text: str) -> str:
        """이슈 진행 경과를 요약합니다."""
        if not history_text or not history_text.strip():
            return "진행 이력 없음"

        system_prompt = '당신은 프로젝트 진행 상황을 정리하는 전문가입니다. 형식: "- YYYY-MM-DD HH:mm:ss : [핵심 내용]"'
        user_prompt = f"다음 히스토리를 요약해주세요:\n\n{history_text}"

        try:
            return self._call_claude(system_prompt, user_prompt).strip()
        except Exception as e:
            logging.error(f"진행 경과 요약 실패: {e}")
            return "진행 경과 요약 실패"

    def analyze_issue_comprehensive(self, issue_summary: str, description: str, history_text: str) -> str:
        """이슈 내용과 진행 상황을 종합적으로 분석하여 요약합니다."""
        system_prompt = "당신은 숙련된 프로젝트 매니저입니다. 이슈 제목, 설명, 이력을 종합 분석하여 핵심 요약을 제공하세요."
        user_prompt = f"제목: {issue_summary}\n설명: {description}\n이력: {history_text}"

        try:
            return self._call_claude(system_prompt, user_prompt).strip()
        except Exception as e:
            logging.error(f"종합 분석 실패: {e}")
            return "종합 분석 중 오류 발생"

    def analyze_pr_code_review(
        self, jira_context: dict, diff_content: str, pr_info: dict
    ) -> str:
        """PR 코드를 Jira 요구사항 대비 분석하여 코드 리뷰 결과를 반환합니다."""
        system_prompt = """당신은 10년 이상의 경력을 가진 시니어 소프트웨어 엔지니어이자 코드 리뷰 전문가입니다.
단순한 문법 오류 탐지를 넘어, 비즈니스 로직의 정합성과 장기적인 유지보수성을 중심으로 리뷰합니다.
리뷰는 건설적이고 구체적이어야 하며, 문제 지적 시 반드시 개선 방향 또는 예시 코드를 함께 제시하세요.

---

## 분석 기준

### 1. Jira 요구사항 매칭 분석
- Jira 이슈의 요구사항과 PR 변경사항이 정확히 대응되는지 검증
- 누락된 요구사항, 초과 구현(scope creep), 의도와 다른 구현이 있는지 확인

### 2. 정적 분석

#### Java
- 안정성: NullPointerException 위험, Optional 미사용, 방어 코드 누락
- 리소스 관리: try-with-resources 미사용, DB 커넥션/스트림 누수 가능성
- 동시성: 공유 자원에 대한 동기화 누락
- 예외 처리: 과도한 catch(Exception e), 예외 무시
- 보안: SQL Injection, XSS, 민감 정보 로그 출력
- 성능: N+1 쿼리 패턴, 불필요한 루프 내 DB 호출

#### Vue
- 반응성: ref/reactive 미사용, watch/computed 오용
- 메모리 누수: onUnmounted에서 리스너/타이머 해제 여부
- Props: 타입 정의 및 required/default 설정
- 보안: v-html 사용 시 XSS 위험

### 3. 코드 컨벤션 검사
- 네이밍, 함수 설계, 코드 중복, 불필요한 코드, 하드코딩

### 4. 테스트 커버리지 검토
### 5. 아키텍처 & 설계 관점

---

## 응답 형식 (HTML)

반드시 아래 HTML 구조를 따라 응답하세요. 마크다운이 아닌 순수 HTML로 작성합니다.

<h3>✅ 1. Jira 요구사항 매칭 분석</h3>
<div class="review-card">
  <div class="review-item">
    <span class="badge-fulfill">✅ 충족</span> 또는 <span class="badge-partial">⚠️ 부분 충족</span> 또는 <span class="badge-miss">❌ 미충족</span>
    <p>요구사항별 상세 설명</p>
  </div>
</div>

<h3>🔍 2. 코드 정적 분석</h3>
<div class="review-card">
  <div class="review-item">
    <span class="severity-critical">🔴 Critical</span> / <span class="severity-major">🟠 Major</span> / <span class="severity-minor">🟡 Minor</span>
    <strong>파일명</strong> (라인 번호)
    <p>이슈 내용</p>
    <div class="suggestion">💡 개선 방안</div>
  </div>
</div>

<h3>📐 3. 코드 컨벤션 검사</h3>
<h3>🧪 4. 테스트 커버리지 검토</h3>
<h3>🏗️ 5. 아키텍처 & 설계 관점</h3>
<h3>📋 6. 종합 의견</h3>
"""

        max_diff_chars = 6000
        truncated_diff = diff_content[:max_diff_chars] if diff_content else "(diff 없음)"
        if diff_content and len(diff_content) > max_diff_chars:
            truncated_diff += "\n\n... [diff가 너무 길어 일부만 표시됨] ..."

        changed_files = ""
        if pr_info.get('changes'):
            file_list = []
            for change in pr_info['changes'][:20]:
                path = change.get('path', {})
                if isinstance(path, dict):
                    path = path.get('toString', '')
                change_type = change.get('type', 'MODIFY')
                file_list.append(f"- [{change_type}] {path}")
            changed_files = "\n".join(file_list)

        user_prompt = f"""## Jira 이슈 정보
- 이슈 키: {jira_context.get('issue_key', 'N/A')}
- 제목: {jira_context.get('summary', 'N/A')}
- 설명: {(jira_context.get('description', '') or '')[:1000]}

## PR 정보
- PR 제목: {pr_info.get('title', 'N/A')}
- 브랜치: {pr_info.get('from_ref', '?')} -> {pr_info.get('to_ref', '?')}

## 변경 파일 목록
{changed_files}

## Diff 내용
```
{truncated_diff}
```

위 내용을 기반으로 코드 리뷰를 수행해주세요."""

        try:
            return self._call_claude(system_prompt, user_prompt).strip()
        except Exception as e:
            logging.error(f"PR 코드 리뷰 분석 실패: {e}")
            return "PR 코드 리뷰 분석 중 오류가 발생했습니다."

    def _build_system_prompt(self) -> str:
        return f"""당신은 JIRA JQL 전문가입니다. 사용자의 자연어 질의를 JQL로 변환하세요.

## 메타데이터
**프로젝트**: {', '.join(self.metadata['projects'])}
**상태**: {', '.join(self.metadata['statuses'])}
**우선순위**: {', '.join(self.metadata['priorities'])}
**이슈 타입**: {', '.join(self.metadata['issue_types'])}
**커스텀 필드**: {json.dumps(self.metadata['custom_fields'], ensure_ascii=False)}

## 규칙
1. 프로젝트 포함: `project = FULFILMENT`
2. '지연' 키워드: `duedate < now() AND status not in (완료, Confirmed, Done)`
3. '담당/담당자' 키워드: `(assignee = "이름" OR cf[12291] = "이름")`
4. 이슈타입: 기능개선, 개발요청, 운영요청 (개발관련=기능개선/개발요청, 운영이슈=운영요청)
5. 관련성 체크: 무관한 질의는 `is_relevant: false`
6. 완료 상태 처리: '완료' 또는 '닫힘' 상태 → `status in (완료, Confirmed, Done)`

## 응답 형식 (JSON만 반환, 코드블록 없이)
{{
    "jql": "...",
    "fields": ["key", "summary", "status", "assignee", "priority", "updated", "issuetype"],
    "explanation": "...",
    "confidence": 0.95,
    "is_relevant": true
}}"""

    def _build_user_prompt(self, natural_query: str, context: Dict[str, Any] = None) -> str:
        today = datetime.now()
        return f"질의: \"{natural_query}\"\n현재 날짜: {today.strftime('%Y-%m-%d')}\nJSON 형식으로만 응답하세요. 코드블록(```)으로 감싸지 마세요."

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Claude 응답에서 JSON 파싱"""
        content = response_text.strip()

        # JSON 코드블록 추출
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # { } 사이의 내용 추출 시도
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return {"jql": "", "explanation": content, "fields": [], "is_relevant": False}

    def _validate_jql(self, jql: str) -> bool:
        if not jql:
            return True
        return 'project' in jql.lower()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = ClaudeQueryParser()
    print(parser.parse_query("이번 주 지연된 이슈"))

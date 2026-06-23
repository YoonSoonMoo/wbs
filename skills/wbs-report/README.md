# wbs-report 스킬 설치 가이드

개발자가 Claude CLI에서 `wbs에 반영해줘` 라고 하면 본인 당일 작업을 WBS에 반영하는 스킬이다.

## 1. 스킬 설치

`wbs-report` 디렉토리를 아래 중 한 곳에 복사한다.

- **개인 전역** (모든 프로젝트에서 사용): `~/.claude/skills/wbs-report/`
- **특정 프로젝트만**: `<프로젝트>/.claude/skills/wbs-report/`

```bash
# 예: 전역 설치
cp -r skills/wbs-report ~/.claude/skills/
```

설치 후 Claude CLI에서 `/skills` 로 `wbs-report` 가 보이면 정상.

## 2. 토큰 발급 (관리자)

WBS 관리자가 **유저 관리 → 대상 개발자 → "토큰 발급"** 을 누르면, 해당 개발자 이메일로 API 토큰이 전송된다.

## 3. 개발자 설정

스킬 디렉토리의 `env.sample.json` 을 `env.json` 으로 복사한 뒤 본인 값으로 채운다.

```bash
cp env.sample.json env.json   # 그리고 env.json 값을 채운다
```

```json
{
  "url": "https://wbs.example.com",
  "project_id": 3,
  "token": "관리자에게_이메일로_발급받은_API_토큰"
}
```

- `url` — WBS 서버 주소
- `project_id` — WBS 그리드 URL `/project/<id>/wbs` 의 `<id>`
- `token` — 2단계에서 이메일로 받은 토큰

> ⚠️ **`env.json` 에는 토큰(비밀번호급 비밀)이 들어간다. 절대 커밋하지 않는다.**
> 스킬을 프로젝트 `.claude/skills/` 에 둔 경우, 프로젝트 `.gitignore` 에 다음을 추가한다:
> ```
> .claude/skills/wbs-report/env.json
> ```
> 전역(`~/.claude/skills/`) 설치는 저장소 밖이라 커밋 위험이 없다.

## 4. 사용

작업 후 Claude CLI에서:

```
wbs에 반영해줘
```

스킬이 ① 내 담당자 확인 → ② 이번주 내 태스크 조회 → ③ handoff.md/git 으로 오늘 작업 파악 →
④ 매칭 제안 → ⑤ 진척률 질문 → ⑥ 승인 후 갱신 → ⑦ 결과 보고 순으로 진행한다.

## 보안

- 토큰은 비밀번호와 동급. `env.json` 은 절대 커밋하지 않는다 (위 `.gitignore` 안내 참고).
- 토큰 유출 시 관리자에게 재발급 요청 → 기존 토큰 즉시 무효화된다.

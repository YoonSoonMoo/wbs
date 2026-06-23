---
name: wbs-report
description: 개발자가 "wbs에 반영해줘", "wbs 업데이트", "진척 보고", "지연업무 확인", "이번주 주요업무 리포팅" 등으로 요청하면 WBS 관리 시스템에서 본인 담당 태스크를 조회·리포팅하거나 진척률·진행상태·실제 일자를 갱신한다. 읽기 전용 조회(지연업무/주간 리포팅)와 갱신(반영) 두 모드를 지원. handoff.md/git 작업 내용과 본인 담당 태스크를 매칭한다. SKILL.md 옆 env.json(url/project_id/token) 설정이 있는 프로젝트에서 동작.
---

# WBS 조회·반영 (wbs-report)

WBS 관리 시스템에서 본인 담당 태스크를 **조회·리포팅**하거나 당일 작업을 **반영(갱신)**한다.

## 모드 분기 (요청 의도로 판단)

| 요청 예 | 모드 | 동작 |
|---|---|---|
| "지연업무 확인", "이번주 주요업무 리포팅", "내 태스크 보여줘" | **A. 조회/리포팅 (읽기 전용)** | §A — `report.py` 로 조회만. 갱신 없음. |
| "wbs에 반영", "진척 50%로 갱신", "오늘 한 거 업데이트" | **B. 반영/갱신** | §0~§7 — 매칭 제안 → 진척률 질문 → 승인 후 PATCH. |

두 모드 모두 §0 설정 로드는 공통. 조회 모드는 **절대 PATCH 하지 않는다** — 갱신이 필요해 보이면 사용자에게 반영 모드 전환을 제안만 한다.

---

## A. 조회/리포팅 모드 (읽기 전용)

SKILL.md 옆 **`report.py`** 헬퍼를 사용한다 (표준 라이브러리만, 크로스플랫폼). env.json 을 자동으로 읽고, `/api/users/me` 로 담당자명을 얻어, 지연업무/이번주 업무를 정렬·요약해 출력한다.

```bash
cd "<skill dir>"            # report.py 가 있는 디렉토리
python3 report.py delayed --today <오늘날짜>   # 지연업무 (plan_end 경과 + 진척<100%)
python3 report.py week    --today <오늘날짜>   # 이번주(월~일) 주요업무
python3 report.py all     --today <오늘날짜>   # 둘 다
```

- `--today` 에는 **시스템 컨텍스트의 현재 날짜**(currentDate)를 넘긴다. 머신 시계와 다를 수 있으므로 명시 권장.
- 담당자 자동 판정이 안 되면 `--assignee <이름>`, 후처리가 필요하면 `--json` 사용.
- 출력의 `[id N]` 이 갱신 시 쓰는 DB `id`(§6) 이다. 화면 TID 번호와 다를 수 있다.
- 헬퍼는 401/빈 배열/연결 실패를 진단 메시지로 알려준다. 그 메시지를 사용자에게 그대로 전달한다.

리포팅 후 사용자가 갱신을 원하면 §5~§6 의 반영 절차로 넘어간다.

---

## B. 반영/갱신 모드

당일 작업을 본인 담당 태스크에 반영한다.
**반드시 담당자 확인 → 매칭 제안 → 진척률 질문 → 승인 후 갱신** 순서를 지킨다. 확인 없이 임의로 쓰지 않는다.

## 0. 설정 로드

이 스킬과 같은 디렉토리의 **`env.json`** 에서 설정을 읽는다 (SKILL.md 옆 파일). 보통 경로:
`~/.claude/skills/wbs-report/env.json` 또는 `<프로젝트>/.claude/skills/wbs-report/env.json`.

```json
{
  "url": "https://wbs.example.com",
  "project_id": 3,
  "token": "관리자에게_이메일로_발급받은_API_토큰"
}
```

- `url` — WBS 서버 베이스 URL. **끝 슬래시는 제거하고 사용** (`http://host:5000/` → `http://host:5000`). 안 그러면 `//api/...` 이중 슬래시로 404/리다이렉트가 날 수 있다.
- `project_id` — 이 작업이 속한 WBS 프로젝트 ID (그리드 URL `/project/<id>/wbs` 의 `<id>`). **items 조회가 빈 배열(`[]`)이면 토큰 문제가 아니라 project_id 가 틀렸을 가능성**을 먼저 의심하고 사용자에게 올바른 id 를 확인한다.
- `token` — 관리자가 발급해 이메일로 받은 API 토큰

검증: `env.json` 이 없거나, `token` 값이 비어 있거나 아직 샘플 안내문(`여기에_...`)이면 사용자에게
"`env.json` 의 url/project_id/token 을 채워주세요" 라고 알리고 중단한다.

이후 호출 편의를 위해 값을 셸 변수로 둔다 (예시):
```bash
WBS_URL=$(... env.json 의 url ...)
WBS_PROJECT_ID=$(... env.json 의 project_id ...)
WBS_TOKEN=$(... env.json 의 token ...)
```
모든 API 호출은 `Authorization: Bearer $WBS_TOKEN` 헤더를 붙인 curl 로 한다:
```bash
curl -s -H "Authorization: Bearer $WBS_TOKEN" "$WBS_URL/api/users/me"
```

## 1. 담당자(나) 확인

```bash
curl -s -H "Authorization: Bearer $WBS_TOKEN" "$WBS_URL/api/users/me"
```
응답의 `name` 이 WBS 상의 **내 담당자명**이다. 401 이 오면 토큰이 잘못/만료된 것 → 사용자에게 관리자 재발급을 안내하고 중단.

## 2. 이번주 내 담당 태스크 조회

```bash
curl -s -H "Authorization: Bearer $WBS_TOKEN" "$WBS_URL/api/wbs/$WBS_PROJECT_ID/items"
```
flat 배열이 온다. 여기서 아래 조건으로 후보를 추린다 (서버 필터 없음 — 여기서 직접 판단):

- `assignee` == 1번에서 얻은 내 이름
- 그리고 다음 중 하나:
  - `plan_start` ~ `plan_end` 기간이 **이번주(월~일)** 와 겹침, 또는
  - `progress` 가 1~99 (진행중), 또는
  - `plan_end` 가 지났는데 `progress` < 100 (지연 중)

오늘 날짜는 시스템 컨텍스트의 현재 날짜를 사용한다(없으면 `date +%F`). 이번주는 월요일~일요일.

후보가 0건이면 사용자에게 알리고, 그래도 반영할 태스크가 있는지 물어본다.

## 3. 오늘 작업 내용 파악 (handoff.md 우선)

1차 소스는 프로젝트의 **`handoff.md`**. 오늘 날짜 섹션 / 최근 작업 항목을 읽어 "오늘 무엇을 했는지" 요약한다.
`handoff.md` 가 없거나 오늘 내용이 불명확하면 보조로 `git log --since=midnight --oneline` 및 미푸시 변경(`git status`)을 참고한다.
그래도 불명확하면 사용자에게 "오늘 어떤 작업을 하셨나요?" 라고 직접 물어본다.

## 4. 매칭 제안

3에서 파악한 작업 내용을 2의 후보 태스크와 매칭해 사용자에게 **제안**한다. 예:

> 오늘 "MQ Consumer 택배접수" 개발을 하신 것으로 보입니다.
> 이번주 담당 태스크 중 아래가 해당되는 것 같은데 맞나요?
> - TID 142 · [택배 연동] MQ Consumer 개발 (현재 진행 40%, 진행상태: 진행중)

- 매칭이 모호하면 후보를 여러 개 제시하고 고르게 한다.
- 이름이 안 맞아 후보가 비면, 어떤 담당자명으로 조회할지 사용자에게 확인한다.

## 5. 진척률·상태 질문

매칭된 태스크별로 **반드시 사용자에게 확인**한다:

- 현재 진행률은 몇 %인가요? (0~100)
- 진행상태 메모를 갱신할까요? (자유 텍스트 — 리스크/이슈/진행 메모)
- 작업을 오늘 시작했다면 실제시작일, 완료했다면 실제종료일을 기록할까요?

사용자가 답하기 전에는 갱신하지 않는다.

## 6. 갱신 (PATCH)

확인된 값만 담아 항목별로 PATCH 한다. `<ITEM_ID>` 는 items 응답의 `id` (TID 화면 번호가 아니라 DB id 필드).

```bash
curl -s -X PATCH \
  -H "Authorization: Bearer $WBS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"progress": 80, "status": "MQ Consumer 1차 개발 완료, QA 대기", "actual_start": "2026-06-23"}' \
  "$WBS_URL/api/wbs/items/<ITEM_ID>"
```

규칙:
- `progress` 0~100 정수.
- 진행을 오늘 처음 시작했고 `actual_start` 가 비어 있으면 오늘 날짜로 채운다.
- `progress` 가 100이면 `actual_end` 를 오늘 날짜로, `status` 를 완료 취지로 갱신할지 물어본다.
- 날짜는 항상 `YYYY-MM-DD`.
- 응답이 200이 아니면 본문 메시지를 사용자에게 그대로 전달한다 (403=권한, 401=토큰).
- **`status` 등 한글·특수문자(em-dash `—`, `·` 등) 가 들어가면 셸 인용(`-d '...'`)에 의존하지 말고 페이로드를 파일로 써서 `--data-binary @file` 로 보낸다.** Content-Type 에 `; charset=utf-8` 을 붙인다. (Windows 셸 인용에서 한글/특수문자가 깨지는 사례 실측.)

```bash
# 한글/특수문자 status 갱신 예 — 페이로드 파일 방식
python3 -c "import json; open('payload.json','w',encoding='utf-8').write(json.dumps({'status':'목표 44.8% / [6/23] skill 고도화 — report.py 신규'}, ensure_ascii=False))"
curl -s -X PATCH -H "Authorization: Bearer $WBS_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @payload.json "$WBS_URL/api/wbs/items/<ITEM_ID>"
```

## 7. 결과 보고

갱신한 태스크 목록(TID, 이름, 변경된 필드: 이전→이후)을 표로 요약한다.

## 주의

- 토큰은 비밀번호급 비밀. 로그/커밋/출력에 평문 토큰을 남기지 않는다.
- 한 번에 여러 태스크를 바꿀 때도 각 태스크 갱신은 사용자 확인을 거친다(일괄 자동 갱신 금지).
- 추측으로 진척률을 채우지 않는다. 항상 담당자에게 묻는다.

## 환경 함정 (실측 기준)

- **대용량 응답**: `items` 응답은 수백 KB(수십~수백 건)에 달할 수 있다. 터미널에 그대로 덤프하지 말고 `report.py`(조회) 또는 파일 저장 후 파싱(갱신 전 확인)으로 처리한다.
- **Windows 한글 깨짐**: PowerShell/터미널에서 한글이 mojibake 로 보이면 `report.py` 가 stdout 을 UTF-8 로 재설정해 해결한다.
- **PATCH 후 검증은 `report.py` 로**: 인라인 `python3 -c` 출력은 `PYTHONIOENCODING=utf-8` 를 붙여도 em-dash(`—`) 같은 문자에서 `UnicodeEncodeError: cp949` 로 죽을 수 있다(실측). 갱신 후 결과 확인은 stdout 을 UTF-8 로 재설정하는 `report.py week|delayed|all` 로 한다. 부득이 `python3 -c` 를 쓸 땐 출력에 특수문자를 넣지 말고 필드 값만 ASCII 라벨로 찍는다.
- **`url` 끝 슬래시**: §0 참조 — `rstrip('/')` 후 사용. `report.py` 는 자동 처리.
- **`project_id` 오설정**: items 가 `[]` 면 토큰이 아니라 project_id 의심 (§0).

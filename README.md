# WBS 관리 시스템

> **Work Breakdown Structure** — 프로젝트의 계층적 작업 분해 구조를 웹에서 생성·관리하는 도구

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-black?logo=flask)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-내장-blue?logo=sqlite)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/tests-128%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/License-Private-red)]()

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [주요 기능](#2-주요-기능)
3. [기술 스택](#3-기술-스택)
4. [프로젝트 구조](#4-프로젝트-구조)
5. [데이터베이스](#5-데이터베이스)
6. [API 엔드포인트](#6-api-엔드포인트)
7. [권한 체계](#7-권한-체계)
8. [빠른 시작](#8-빠른-시작)
9. [환경 설정](#9-환경-설정)
10. [향후 작업](#10-향후-작업)

> 설계 결정의 배경·상세 스펙은 **[handoff.md](./handoff.md)** 를 참조하세요. 본 문서는 개요이며,
> 스키마 전체 컬럼·엔드포인트 전량·변경 이력은 handoff에서 단일 관리합니다.

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | WBS(Work Breakdown Structure) 관리 시스템 |
| 목적 | 프로젝트의 계층적 작업 분해 구조를 웹에서 생성·관리 |
| 저장소 | origin: https://github.com/YoonSoonMoo/wbs · gitea(미러): https://gitea.daou.co.kr/yoonsm/wbs |
| 기간 | 2026-04-10 최초 구축 ~ 2026-08-26 최신 |

프로젝트 관리 담당자가 작업(Task)을 계층적으로 정의하고 일정·담당자·진행률을 한 화면에서
관리할 수 있도록 만든 **경량 웹 애플리케이션**입니다. 별도 빌드 도구 없이 Flask 서버만으로
즉시 실행되며, 엑셀 감각의 그리드 편집을 중심으로 Gantt 차트·통계·AI 어시스턴트·실시간 협업을
함께 제공합니다.

---

## 2. 주요 기능

### 📋 WBS 그리드 — 엑셀 방식 편집

- **계층 구조** — 구분 > Task > 서브태스크 > 세부항목. WBS 코드(`1.0 / 1.1 / 1.1.1`)는 추가·이동·삭제 시 자동 재계산
- **셀 선택 = 클릭, 편집 = 더블클릭·F2·Enter·문자 입력** — 드래그·Shift·방향키로 사각형 범위, `Ctrl+A` 전체
- **`Ctrl+C` TSV 복사 / `Ctrl+V` 붙여넣기 / `Delete` 범위 삭제** — 엑셀과 그대로 오간다
- **자동 저장** — 편집 종료 시 300ms debounce로 PATCH. 날짜는 다양한 입력 형식을 `yyyy-MM-dd`로 정규화
- **행 조작** — TID 열 클릭 복수 선택, 드래그앤드롭·우클릭 메뉴(삽입/복제/삭제/행이동)
- **필터·정렬** — 빠른검색 2입력 AND, 완료 포함·나만의·이번주·지연 필터, 컬럼별 정렬 (상태는 프로젝트별 localStorage 유지)

### 🤖 AI 어시스턴트

- 자연어 한 줄로 **조회 · 추가 · 수정 · 삭제 · 순서 이동 · 마일스톤 기반 태스크 일괄 생성**
- 조회 결과는 그리드에 즉시 필터로 적용되고, 지연·리스크에 대한 **분석 코멘트(insight)** 를 함께 제시
- 프로바이더 4종을 `.env` 한 줄로 전환: `GEMINI` · `DAOU_GATEWAY`(사내 게이트웨이) · `CLAUDE` · `LOCAL`(Claude CLI)
- **LLM은 자연어→JSON 변환만** 담당하고 DB 조작은 전부 서버 코드가 수행 (담당자·공수·진행률 등은 서버 고정값)

### 🔄 실시간 협업 (SSE)

- 다른 사용자의 변경이 **새로고침 없이** 그리드에 반영 (본인 변경은 무시)
- **편집 중 셀 표시** — 편집자별 색상 외곽선 + 이름 배지
- 내가 편집 중이면 즉시 덮어쓰지 않고 "지금 갱신" 배너로 알린 뒤 편집 종료 시 반영

### 📊 대시보드 · 통계

- 프로젝트 카드 (전체/완료/진행/지연 건수, 공수 가중 평균 진행률)
- 카테고리별·담당자별 통계, 주간 진척 추이 (Chart.js 도넛·라인)
- 계획 대비 실제 일정 갭 분석 (지연/조기/정시)

### 📅 Gantt 차트

- [Frappe Gantt](https://frappe.io/gantt) 기반 (로컬 번들, 한국어 로케일 패치)
- 담당자별 색상, 완료 항목 토글, 오늘 세로선, 담당자 필터

### 📧 알림 · 메일

- **태스크 갱신 알림 자동 메일** — 프로젝트별 지정 시각에 담당자에게 이번주 할당 태스크를 발송 (APScheduler, 평일 1회)
- **지연 태스크 메일** — 담당자별 지연 목록 수동 발송
- 오늘의 알림 칩 — 지연·임박 태스크를 그리드 상단에 상시 표시

### 📥 Import / Export · 운영

| 항목 | 내용 |
|------|------|
| Export | CSV(UTF-8 BOM) · Excel(.xlsx, 서식 포함) |
| Import | CSV 업로드 · 탭 구분 텍스트 붙여넣기 · 샘플 `.xlsx` 다운로드 |
| 변경 이력 | 추적 필드 6종 기록 (프로젝트별 ON/OFF) |
| 백업/복원 | DB 스냅샷 다운로드·업로드 복원 (구버전 백업은 마이그레이션 자동 적용) |
| 공지사항 | 그리드 상단 marquee |

### 🔐 인증 / 권한

- 세션 기반 인증 (Flask session + werkzeug 해싱), 비활성 계정 차단, 임시 비밀번호 강제 변경
- **5단계 권한** admin > PM > PL > developer > viewer — 상세는 [§7](#7-권한-체계)
- **API 토큰** — `Authorization: Bearer <token>`으로 외부 클라이언트(Claude CLI 스킬 등)가 세션 없이 호출

---

## 3. 기술 스택

| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Language | Python | 3.11 | 3.10+ |
| Framework | Flask | 3.1.1 | 앱 팩토리 패턴 |
| Database | SQLite | 내장 | `sqlite3` 직접 사용 (ORM 없음), WAL 모드 |
| Frontend | Jinja2 + Vanilla JS | — | 서버 렌더링 + AJAX 하이브리드 |
| Excel | openpyxl | 3.1.5 | Import / Export |
| LLM SDK | openai / anthropic | 1.59.6 / 0.120.2 | openai=GEMINI·DAOU_GATEWAY, anthropic=CLAUDE |
| Gantt | Frappe Gantt | 0.6.1 | 로컬 번들 (ko 로케일 패치) |
| Chart | Chart.js | 4.4.1 | CDN, 통계 모달 |
| Font | Noto Sans KR + JetBrains Mono | — | Google Fonts CDN |
| 스케줄러 | APScheduler | 3.10.4 | 태스크 갱신 알림 |
| HTTP | requests | 2.34.2 | 메일 발송(NCP API) |
| 환경변수 | python-dotenv | 1.1.0 | |
| WSGI | waitress | 3.0.2 | 로컬 Windows · Docker 공통 |
| 배포 | Docker + Coolify | — | `Dockerfile` + `docker-compose.yaml` |
| Test | pytest | 8.3.5 | 128건 |

> **SPA 프레임워크 미사용** — 빌드 도구 없이 즉시 개발·실행 가능

---

## 4. 프로젝트 구조

```
wbs/
├── app/
│   ├── __init__.py              # Flask 앱 팩토리 (admin 시드, 스케줄러 기동)
│   ├── auth.py                  # 인증 데코레이터
│   ├── config.py                # 환경설정 (Dev / Prod / Test)
│   ├── extensions.py            # DB 헬퍼 (get_db, close_db, init_db)
│   ├── scheduler.py             # APScheduler (태스크 갱신 알림 1분 폴링)
│   ├── models/                  # 순수 DB CRUD (project, wbs_item, change_history)
│   ├── services/                # 비즈니스 로직
│   │   ├── wbs_service.py           # 트리 구축·이동·일괄수정
│   │   ├── wbs_code_service.py      # WBS 코드 자동생성·재계산
│   │   ├── auth_service.py          # 인증·역할·API 토큰
│   │   ├── dashboard_service.py     # 통계
│   │   ├── ai_assistant.py          # AI 어시스턴트 (멀티 프로바이더 LLM)
│   │   ├── event_broker.py          # SSE 인메모리 Pub/Sub
│   │   ├── notification_service.py  # 태스크 갱신 알림
│   │   ├── mail_service.py          # 메일 발송 + HTML 빌더
│   │   ├── backup_service.py        # DB 백업·복원
│   │   └── import_export.py         # CSV / Excel
│   ├── routes/                  # Blueprint (auth, main, api_project, api_wbs,
│   │                            #            api_users, api_admin, api_import_export)
│   ├── static/                  # css / js (grid, gantt, dashboard, walkthrough) / img
│   └── templates/               # landing, login, register, index, wbs, gantt
├── migrations/                  # NNN_*.sql 버전드 마이그레이션 (001~017)
├── certs/                       # 사내 루트 CA (AI 게이트웨이 TLS용)
├── scripts/make_ca_bundle.py    # certifi + 사내 CA 결합 번들 생성
├── skills/wbs-report/           # Claude CLI 연동 스킬
├── template/                    # UI·스크립트 레퍼런스 원본 (실사용 안 함)
├── tests/                       # pytest 스위트 (128건)
├── instance/                    # SQLite DB (자동 생성, gitignore)
├── Dockerfile / docker-compose.yaml
├── run.py                       # 실행 진입점
├── handoff.md                   # 개발 인수인계 상세 문서
└── CLAUDE.md                    # Claude Code 작업 지침
```

### 핵심 설계 원칙

| 결정 | 이유 |
|------|------|
| **Adjacency List** 계층 구조 | 삽입·이동이 잦은 WBS 특성상 Nested Set보다 단순 |
| **재귀 CTE** 트리 조회 | 단일 쿼리로 전체 트리 반환, N+1 방지 |
| **ORM 미사용** | sqlite3 내장 모듈로 종속성 최소화, 쿼리 가시성 확보 |
| **WAL 모드** | 동시 읽기 성능 향상 |
| **버전드 마이그레이션** | `schema_version` 추적 → 매 기동 시 미적용분만 자동 실행 |
| **LLM은 파서로만** | 자연어→JSON 변환만 맡기고 DB 조작·고정값은 서버가 결정 |
| **앱 팩토리 패턴** | 환경별 설정·테스트 격리 용이 |

---

## 5. 데이터베이스

SQLite 단일 파일(`instance/wbs.db`). 서버 기동 시 `migrations/`의 미적용 SQL이 순서대로 자동 적용됩니다.

| 테이블 | 역할 |
|--------|------|
| `project` | 프로젝트 (개요/마일스톤, 공지, 이력 ON/OFF, 알림 발송시각) |
| `wbs_item` | **WBS 항목** — `parent_id` Adjacency List + `wbs_code`·`sort_order` |
| `user` | 계정 (전역 역할 admin/developer, 활성 여부, API 토큰 해시) |
| `project_member` | 프로젝트별 역할 매핑 — **권한 판정의 실제 출처** |
| `wbs_change_history` | 변경 이력 (추적 필드 6종, 항목 삭제 후에도 보존) |
| `schema_version` | 마이그레이션 적용 이력 |

- 트리거: `progress` 100 도달/이탈 시 `completed_at` 자동 설정·해제
- 인덱스: `idx_wbs_project` · `idx_wbs_parent` · `idx_wbs_code` · `idx_wbs_assignee` · `idx_wbs_sort`

> 컬럼 단위 전체 정의는 [handoff.md §4](./handoff.md) 참조

---

## 6. API 엔드포인트

| 그룹 | 프리픽스 | 주요 기능 |
|------|---------|----------|
| 페이지 | `/` | 랜딩·대시보드·WBS 그리드·Gantt |
| 인증 | `/login` `/register` `/logout` | 세션 로그인 |
| 프로젝트 | `/api/projects` | 목록·CRUD·멤버 관리·이력 플래그 |
| WBS | `/api/wbs` | 항목 CRUD·이동·일괄수정·통계·지연·AI·이력 |
| 실시간 | `/api/wbs/<pid>/events` `/editing` | SSE 변경 스트림 · 편집 presence |
| 유저 | `/api/users` | 목록·권한·활성 토글·비밀번호 리셋·API 토큰 |
| 시스템 | `/api/admin` | DB 백업 · 복원 (admin) |
| Import/Export | `/api/io` | CSV·Excel 내보내기 / 가져오기 / 샘플 |

**인증** — 세션 쿠키 또는 `Authorization: Bearer <API 토큰>` 둘 다 허용

> 메서드·URL·권한 단위 전체 목록은 [handoff.md §5](./handoff.md) 참조

---

## 7. 권한 체계

```
admin        전역 전권 — 유저 관리 · 백업/복원 · 새 프로젝트 생성
 └ PM        프로젝트 전권 — 수정·삭제·초기화·이력·메일·AI·멤버 관리
    └ PL     개발자 권한 + AI 어시스턴트 + 계획일자 수정
       └ developer   WBS 편집 (계획시작/완료일은 수정 불가)
          └ viewer   읽기 전용 (Gantt 접근 차단, 쓰기 API 403)
```

- **PM/PL/developer/viewer는 프로젝트별 역할**(`project_member.role`)이며 판정의 실제 출처입니다
- **전역 역할(`user.role`)은 관리자/일반 2단계**로, 시스템 관리자 여부만 구분합니다
- 멤버 추가·삭제 및 역할 지정은 **프로젝트 수정 화면에서 admin/PM**이 수행합니다

| 데코레이터 | 용도 |
|-----------|------|
| `@login_required` | 페이지 라우트 인증 |
| `@api_login_required` | API 인증 (401 JSON) — 세션 또는 Bearer 토큰 |
| `@project_access_required(min_role)` | 프로젝트별 최소 권한 검사 |
| `@admin_required` | 전역 admin 검사 |

### 기본 관리자 계정

서버 최초 실행 시 자동 생성됩니다 (`ADMIN_*` 환경변수로 변경 가능).

| 항목 | 값 |
|------|-----|
| 이메일 | `yoonsm@daou.co.kr` |
| 비밀번호 | `zaq12wsx` |
| 역할 | admin |

> ⚠️ **운영 환경에서는 반드시 비밀번호를 변경하세요.**

---

## 8. 빠른 시작

### 로컬 개발

```bash
git clone https://github.com/YoonSoonMoo/wbs.git
cd wbs

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
python run.py                   # http://localhost:5000
```

> 최초 실행 시 `instance/wbs.db`가 생성되고 `migrations/`가 순서대로 적용된 뒤 관리자 계정이 시드됩니다.

### 사내 AI Gateway를 쓰는 경우

사내망은 자체 루트 CA로 TLS를 가로채므로, **CA 번들을 먼저 만들어야** AI 호출이 성공합니다.
(없으면 `Connection error.`로 실패합니다.)

```bash
python scripts/make_ca_bundle.py    # -> certs/ca-bundle.pem
```

```dotenv
AI_MODEL=DAOU_GATEWAY
AI_API_KEY=sk-...
SSL_CERT_FILE=certs/ca-bundle.pem
```

### Docker 배포

```bash
docker compose up -d --build        # waitress-serve, 5000 포트, wbs-data 볼륨에 DB 영속
```

컨테이너 TZ는 `Asia/Seoul` 고정입니다. `FLASK_ENV`/`HOST`/`PORT`/`DATABASE_PATH`는 compose가
덮어쓰고 나머지는 `.env` → 없으면 코드 기본값을 씁니다.

### 테스트

```bash
python -m pytest -q                 # 128건
```

---

## 9. 환경 설정

`FLASK_ENV`로 실행 환경을 선택합니다.

| 값 | 설정 클래스 | DB |
|----|-----------|-----|
| `development` (기본값) | `DevelopmentConfig` | `instance/wbs.db` |
| `production` | `ProductionConfig` | `instance/wbs.db` |
| `testing` | `TestingConfig` | `:memory:` |

### 환경변수 (`.env`)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECRET_KEY` | dev 키 | Flask 세션 서명 — **운영 시 반드시 변경** |
| `FLASK_ENV` | `development` | 실행 환경 |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | 바인딩 주소 |
| `DATABASE_PATH` | `instance/wbs.db` | SQLite 파일 경로 |
| `ADMIN_NAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | 초기 관리자 시드 값 |
| `AI_MODEL` | `LOCAL` | `GEMINI` \| `DAOU_GATEWAY` \| `CLAUDE` \| `LOCAL` |
| `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL_NAME` | — | 프로바이더별 인증·엔드포인트·모델 |
| `SSL_CERT_FILE` | — | 사내 CA 결합 번들 (DAOU_GATEWAY 사용 시 필수) |
| `APP_BASE_URL` | (없음) | 메일 내 링크의 서비스 기본 URL. 미설정 시 수동 발송은 요청 호스트, 스케줄러는 `http://localhost:5000` |
| `APP_TZ` | `Asia/Seoul` | 스케줄러 발송시각 판단 기준 시간대 |
| `ENABLE_SCHEDULER` | `1` | `1` 이외의 값이면 알림 스케줄러 미기동 (테스트·reloader 부모 프로세스도 자동 제외) |
| `VERSION` | — | 그리드 상단바에 표시할 버전 문자열 |
| `NAVER_API_ACCESS_KEY` / `NAVER_API_SECRET_KEY` | — | 메일 발송(NCP Cloud Outbound Mailer) 인증 |

---

## 10. 향후 작업

| 항목 | 우선순위 |
|------|---------|
| 멀티 프로세스 확장 (SSE 브로커·스케줄러가 단일 프로세스 전제 → Redis Pub/Sub·외부 스케줄러 선행) | 높음 |
| 사내 AI Gateway 앱 서버 방화벽 결재 | 높음 |
| 에러 핸들링 고도화 (전역 에러 핸들러) | 중간 |
| Excel Import UI (파일 업로드 폼) | 중간 |
| AI 어시스턴트 동시성 (LOCAL/CLI 한정, 중기 Celery/RQ 작업 큐) | 중간 |
| 변경 이력 archival / rotation 정책 | 낮음 |
| 대시보드 페이지 차트 (통계 모달은 구현됨) | 낮음 |
| 인쇄 / PDF 보고서 출력 | 낮음 |

---

## 관련 문서

- [handoff.md](./handoff.md) — 개발 인수인계 상세 문서 (스키마·API 전량, 설계 결정 배경, 변경 이력)
- [CLAUDE.md](./CLAUDE.md) — Claude Code 작업 지침
- [migrations/](./migrations/) — 버전드 DB 스키마 (001~017)

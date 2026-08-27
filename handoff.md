# WBS 관리 시스템 - Handoff 문서

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | WBS(Work Breakdown Structure) 관리 시스템 |
| 목적 | 프로젝트의 계층적 작업 분해 구조를 웹에서 생성/관리하는 도구 |
| 저장소 | origin: https://github.com/YoonSoonMoo/wbs.git · gitea(미러): https://gitea.daou.co.kr/yoonsm/wbs.git |
| 기간 | 2026-04-10 최초 구축 ~ 2026-08-26 최신. 상세 변경 이력은 **§8 변경 이력** 참조 |

## 2. 기술 스택

| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Language | Python | 3.x | |
| Framework | Flask | 3.1.1 | 앱 팩토리 패턴 |
| Database | SQLite | 내장 | `sqlite3` 모듈 직접 사용 (ORM 없음) |
| Frontend | Jinja2 + Vanilla JS | | 서버 렌더링 + AJAX 하이브리드 |
| Font | Noto Sans KR + JetBrains Mono | | Google Fonts CDN |
| Excel | openpyxl | 3.1.5 | Excel Import/Export |
| LLM SDK | openai / anthropic | 1.59.6 / 0.120.2 | AI 어시스턴트 — openai=GEMINI·DAOU_GATEWAY, anthropic=CLAUDE |
| Gantt | Frappe Gantt | 0.6.1 | 로컬 번들 (한국어 로케일 패치) |
| Chart | Chart.js | 4.4.1 | CDN, 통계 모달 차트 (도넛, 라인) |
| 스케줄러 | APScheduler | 3.10.4 | 태스크 갱신 알림 백그라운드 발송 |
| HTTP | requests | 2.34.2 | 메일 발송(NCP API) 호출 |
| 환경변수 | python-dotenv | 1.1.0 | |
| WSGI | waitress | 3.0.2 | 로컬 Windows · Docker 공통 프로덕션 서버 |
| 배포 | Docker + Coolify | | `Dockerfile`(python:3.11-slim, TZ=Asia/Seoul) + `docker-compose.yaml` |
| Test | pytest | 8.3.5 | 128건 |

## 3. 디렉토리 구조

```
wbs/
├── app/
│   ├── __init__.py              # Flask 앱 팩토리 (create_app, admin 시드, context_processor, 스케줄러 기동)
│   ├── scheduler.py             # APScheduler 백그라운드 스케줄러 (태스크 갱신 알림 1분 폴링)
│   ├── auth.py                  # 인증 데코레이터 (login_required, project_access_required 등)
│   ├── config.py                # 환경설정 (Dev/Prod/Test)
│   ├── extensions.py            # DB 헬퍼 (get_db, close_db, init_db)
│   ├── models/
│   │   ├── project.py           # 프로젝트 CRUD 쿼리 (history_enabled 플래그 포함)
│   │   ├── wbs_item.py          # WBS 항목 CRUD 쿼리 (재귀 CTE 트리 조회, _trim/_normalize_date 헬퍼)
│   │   └── change_history.py    # WBS 변경 이력 CRUD (record_changes, list_changes, count_changes)
│   ├── services/
│   │   ├── wbs_service.py       # WBS 핵심 비즈니스 로직 (트리 구축, 이동, 일괄수정)
│   │   ├── wbs_code_service.py  # WBS 코드 자동생성/재계산 로직
│   │   ├── auth_service.py      # 인증 서비스 (register, login, get_project_role, API 토큰 등)
│   │   ├── dashboard_service.py # 대시보드 통계 (카테고리별, 담당자별, 지연업무)
│   │   ├── backup_service.py    # DB 백업/복원 (sqlite backup API 스냅샷, 복원 시 마이그레이션 자동 적용)
│   │   ├── ai_assistant.py      # AI 어시스턴트 (멀티 프로바이더 LLM, 자연어 → WBS CRUD/move)
│   │   ├── import_export.py     # CSV/Excel Import/Export
│   │   ├── mail_service.py      # 메일 발송 (NCP API) + HTML 빌더 (지연 알림/이번주 갱신요청)
│   │   ├── notification_service.py # 태스크 갱신 알림 (이번주 할당 태스크 담당자별 발송, 스케줄러가 호출)
│   │   └── event_broker.py      # 실시간 이벤트 인메모리 Pub/Sub 브로커 (SSE용, 프로젝트별 구독 큐)
│   ├── routes/
│   │   ├── __init__.py          # 블루프린트 등록 (register_blueprints)
│   │   ├── auth.py              # 인증 라우트 (/login, /register, /logout)
│   │   ├── main.py              # 페이지 라우트 (/=landing 또는 /dashboard, /dashboard, /project/<id>/wbs, /gantt)
│   │   ├── api_project.py       # 프로젝트 REST API (/api/projects)
│   │   ├── api_wbs.py           # WBS REST API (/api/wbs, SSE /events·/editing 포함)
│   │   ├── api_users.py         # 유저 관리 REST API (/api/users, admin 전용)
│   │   ├── api_admin.py         # 시스템 백업/복원 API (/api/admin, admin 전용)
│   │   └── api_import_export.py # Import/Export API (/api/io)
│   ├── static/
│   │   ├── css/                 # style.css(대시보드/랜딩/인증), wbs.css(그리드), frappe-gantt.min.css
│   │   ├── img/                 # logo2.png(로고·파비콘), AI_assistant.png(랜딩 쇼케이스)
│   │   └── js/
│   │       ├── app.js               # API 헬퍼, 토스트 알림, 유틸리티
│   │       ├── grid.js              # WBS 그리드 UI (인라인편집, 확장편집, 복수선택, SSE 실시간 갱신/편집 presence)
│   │       ├── gantt.js             # Gantt 차트 (담당자별 색상, 완료 토글, 오늘 세로선, 담당자 필터)
│   │       ├── frappe-gantt.min.js  # Frappe Gantt 라이브러리 (로컬, ko 로케일 패치)
│   │       ├── walkthrough.js       # 초회 방문자용 온보딩 투어 (localStorage 기반)
│   │       └── dashboard.js         # 대시보드 (프로젝트 목록, 통계카드, 유저 관리 모달)
│   └── templates/
│       ├── base.html            # 기본 레이아웃 (대시보드용, 파비콘, 강제 PW변경 모달)
│       ├── landing.html         # 랜딩 페이지 (비로그인 /, 기능 소개 + AI 쇼케이스)
│       ├── login.html / register.html # 인증 페이지 (Easy WBS 브랜드)
│       ├── index.html           # 대시보드 페이지 (/dashboard)
│       ├── wbs.html             # WBS 그리드 뷰 (독립 페이지, 상단바 메뉴, 역할별 UI 게이팅)
│       └── gantt.html           # Gantt 차트 뷰 (viewer 접근 차단)
├── migrations/                  # NNN_*.sql 버전드 마이그레이션 (001~017, §4 참조)
├── certs/                       # daou-root.pem(사내 루트 CA, 커밋) / ca-bundle.pem(결합본, gitignore)
├── scripts/make_ca_bundle.py    # certifi + 사내 CA 결합 번들 생성 (SSL_CERT_FILE용, §6 AI 참조)
├── instance/                    # SQLite DB 파일 (자동 생성, gitignore)
├── tests/                       # pytest 테스트 스위트 (conftest + 10개 파일, 128건)
├── skills/wbs-report/           # Claude CLI 연동 스킬 (env.json은 토큰 포함 gitignore)
├── template/                    # UI·스크립트 레퍼런스 원본 (wbs-manage.html 등, 실사용 안 함)
├── Dockerfile                   # python:3.11-slim + tzdata(KST) + waitress-serve
├── docker-compose.yaml          # Coolify 배포용 (env_file .env, wbs-data 볼륨, healthcheck)
├── requirements.txt             # 의존성
├── run.py                       # 실행 진입점
├── README.md                    # 공개용 소개 문서
├── CLAUDE.md                    # Claude Code 작업 지침 (요약 + 이 문서 참조)
└── handoff.md                   # 이 문서
```

## 4. DB 스키마

### project 테이블
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 프로젝트명 |
| description | TEXT | 설명 (AI 분석용 개요/마일스톤 기입 유도) |
| start_date / end_date | TEXT | 시작/종료일 (YYYY-MM-DD) |
| created_at / updated_at | TEXT | 생성/수정 일시 (updated_at 트리거 자동) |
| history_enabled | INTEGER | 변경 이력 기록 ON/OFF (기본 0) |
| notice | TEXT | 그리드 상단 marquee 공지사항 (빈 문자열이면 미표시) |
| task_notify_enabled | INTEGER | 태스크 갱신 알림 자동 메일 ON/OFF (기본 0) |
| task_notify_time | TEXT | 알림 발송 시각 'HH:MM' (기본 09:00, 평일에만 발송) |

### wbs_item 테이블 (핵심)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| project_id | INTEGER FK | 소속 프로젝트 |
| parent_id | INTEGER FK | 부모 항목 (NULL=최상위) → Adjacency List 패턴 |
| wbs_code | TEXT | 자동생성 코드 (1.0, 1.1, 1.1.1 등) |
| level | INTEGER | 깊이 (0=최상위) |
| sort_order | INTEGER | 형제 노드 내 정렬순서 |
| category | TEXT | 구분 (기획, 설계, 개발 등) |
| task_name | TEXT | Task명 |
| subtask | TEXT | 서브태스크 |
| detail | TEXT | 세부항목 |
| description | TEXT | 상세 설명 |
| plan_start / plan_end | TEXT | 계획 시작/완료일 |
| actual_start / actual_end | TEXT | 실제 시작/종료일 |
| assignee | TEXT | 담당자 |
| effort | REAL | 공수 (man-day) |
| progress | INTEGER | 진행률 (0~100) |
| status | TEXT | 진행상태 (대기/진행중/완료/보류/지연) |
| priority | TEXT | 우선순위 (low/medium/high/critical) |
| is_milestone | INTEGER | 마일스톤 여부 (0/1) |
| updated_by | TEXT | 최종 수정자 이름 (세션 user_name) |
| completed_at | TEXT | 완료 일시 (트리거 자동, progress=100 시 설정) |

### user 테이블 (인증)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 이름 |
| email | TEXT UNIQUE | 이메일 (로그인 ID) |
| password_hash | TEXT NOT NULL | 비밀번호 해시 (werkzeug) |
| role | TEXT | 전역 역할 (admin/developer/viewer), CHECK 제약 |
| is_active | INTEGER | 활성 여부 (0=비활성, 로그인 차단) |
| requires_password_change | INTEGER | 임시 비밀번호 강제 변경 플래그 |
| api_token_hash | TEXT | 외부 클라이언트 API 토큰의 SHA-256 해시 (평문 미저장, `idx_user_api_token`) |
| created_at | TEXT | 생성일시 |

### project_member 테이블 (프로젝트 멤버 매핑)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| project_id / user_id | INTEGER FK | 복합 PK |
| role | TEXT | **프로젝트별 역할(pm/pl/developer/viewer) — 권한 판정의 실제 출처** |

- admin은 project_member 없이도 모든 프로젝트 접근 가능. 그 외는 등록된 프로젝트만
- **권한 판정 = `project_member.role`(프로젝트별)**. 전역 `user.role`은 admin 여부 + 기본값

### wbs_change_history 테이블 (변경 이력)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| project_id | INTEGER FK | 소속 프로젝트 (CASCADE) |
| item_id | INTEGER FK | 대상 항목 (SET NULL, 항목 삭제돼도 이력 보존) |
| changed_at / changed_by | TEXT | 변경 일시(localtime) / 주체(user_name) |
| field | TEXT | 변경 필드 (`detail/assignee/plan_start/plan_end/effort/progress` 중 하나) |
| old_value / new_value | TEXT | 변경 전/후 값 |
| snapshot_detail / snapshot_assignee | TEXT | 변경 시점 세부항목/담당자 스냅샷 (검색·식별용) |

- 추적 필드 6개(`TRACKED_FIELDS`)만 기록. `_is_history_enabled(project_id)`가 ON일 때만 (`wbs_service`에서 호출)
- 인덱스: `idx_hist_project(project_id, changed_at DESC)`, `idx_hist_item(item_id)`

### schema_version 테이블
- 마이그레이션 파일 번호(version PK)와 적용 일시(applied_at) 추적. `init_db()`가 미적용 `NNN_*.sql`만 순서대로 실행

### 트리거 / 인덱스
- `trg_wbs_completed` / `trg_wbs_uncompleted` — progress 100 도달/이탈 시 `completed_at` 설정/초기화
- 인덱스: `idx_wbs_project`, `idx_wbs_parent`, `idx_wbs_code(project_id, wbs_code)`, `idx_wbs_assignee`, `idx_wbs_sort(parent_id, sort_order)`

### 마이그레이션 목록 (`migrations/`)
`001_initial`(project/wbs_item) · `002_auth`(user/project_member) · `003_stats`(updated_by/completed_at/트리거) · `004_user_mgmt`(is_active, participant→developer) · `005_password_reset`(강제 변경 플래그) · `006_member_admin_role`(role CHECK 확장) · `007_remove_admin_members` · `008_unify_user_role`(권한 단일관리) · `009_normalize_dates`(YY-MM-DD 정정) · `010_change_history` · `011_project_history_flag` · `012_project_notice` · `013_api_token` · `014_task_notify` · `015_pm_pl_roles`(project_member.role CHECK를 pm/pl 포함으로 확장) · `016_collapse_global_role`(전역 role viewer→developer 통일) · `017_task_notify_last_date`(알림 발송일 기록 컬럼)

## 5. API 엔드포인트

### 인증/페이지 라우트
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/` | 비로그인: 랜딩 / 로그인: `/dashboard`로 리다이렉트 |
| GET | `/dashboard` | 대시보드 (프로젝트 목록) |
| GET | `/project/<id>/wbs` | WBS 그리드 페이지 |
| GET | `/project/<id>/gantt` | Gantt 차트 (viewer는 `/`로 리다이렉트) |
| GET/POST | `/login` `/register` | 로그인 / 회원가입 |
| GET | `/logout` | 로그아웃 |

### 프로젝트 API (`/api/projects`)
| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/api/projects` | 목록(로그인) / 생성(**admin**) |
| GET/PUT/DELETE | `/api/projects/<id>` | 상세(로그인) / 수정·삭제(**pm 이상**) |
| PATCH | `/api/projects/<id>/history-flag` | 변경 이력 ON/OFF (**pm 이상**, body `{enabled}`) |
| GET | `/api/projects/<id>/members` · `/api/projects/users` | 멤버 목록 / 전체 사용자 |
| GET | `/api/projects/scheduler/status` | 태스크 알림 스케줄러 상태 (admin) |

### WBS API (`/api/wbs`)
| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/api/wbs/<pid>/items` | 목록(?mode=flat/tree) / 추가 |
| GET/PUT/PATCH/DELETE | `/api/wbs/items/<id>` | 상세 / 전체수정 / 부분수정(인라인) / 삭제(재귀) |
| — | (항목 단위 라우트) | URL에 project_id가 없어 데코레이터 대신 `_check_item_write()`가 항목→프로젝트를 역추적해 권한 검사 |
| POST | `/api/wbs/items/<id>/move` | 항목 이동 (parent_id, sort_order) |
| POST | `/api/wbs/<pid>/items/batch` | 일괄 수정 |
| DELETE | `/api/wbs/<pid>/items` | WBS 전체 초기화 (**pm 이상**) |
| GET | `/api/wbs/<pid>/stats` · `/delayed` · `/dashboard` · `/schedule-gaps` | 통계 / 지연목록 / 종합 / 계획vs실제 갭 |
| GET | `/api/wbs/<pid>/weekly-stats` | 주간 진척 통계 (?weeks=4) |
| POST | `/api/wbs/<pid>/send-delay-mail` · `/send-task-update-mail` | 지연/갱신요청 메일 발송 (**pm 이상**) |
| POST | `/api/wbs/<pid>/ai` | AI 어시스턴트 자연어 질의 (조회/추가/**마일스톤 기반 생성**/삭제/수정/이동, pl 이상) |
| GET | `/api/wbs/<pid>/history` | 변경 이력 조회 (developer 이상, `?limit&offset`) |
| **GET** | **`/api/wbs/<pid>/events`** | **SSE 실시간 변경 스트림 (viewer 이상 구독)** |
| **POST** | **`/api/wbs/<pid>/editing`** | **셀 편집 presence 신호 (developer 이상, body `{item_id, col, editing}`)** |

### 유저 관리 API (`/api/users`, admin 전용, 일부 예외)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/users` | 유저 목록 |
| PUT | `/api/users/<id>/role` · `/active` | 권한 변경 / 활성 토글 (본인 비활성화 금지) |
| POST | `/api/users/<id>/reset-password` | 비밀번호 리셋 (10자리 난수 자동생성·메일발송) |
| PUT | `/api/users/me/password` | 본인 비밀번호 변경 (강제 플래그 해제) |
| GET | `/api/users/me` | 현재 인증 주체 `{id,name,email,role}` (담당자 식별용, 로그인 유저 전체) |
| POST/DELETE | `/api/users/<id>/api-token` | API 토큰 발급(이메일 전송)/폐기 (admin) |

### 시스템 관리 API (`/api/admin`, admin 전용)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/admin/backup` | DB 스냅샷 다운로드 (sqlite backup API — WAL 상태와 무관하게 정합성 보장) |
| POST | `/api/admin/restore` | 백업 파일 업로드 복원 (유효성 검증 후 교체, 구버전이면 마이그레이션 자동 적용) |

### Import/Export API (`/api/io`)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/io/<pid>/export/csv` · `/export/excel` | CSV(UTF-8 BOM) / Excel(.xlsx) 다운로드 |
| GET | `/api/io/sample/excel` | 붙여넣기용 샘플 `샘플.xlsx` 다운로드 (헤더 + 예시 2행, 프로젝트 무관·로그인만 필요) |
| POST | `/api/io/<pid>/import/csv` · `/import/paste` | CSV 업로드 / 탭 구분 텍스트 가져오기 |

## 6. 핵심 설계 결정

### 계층 구조: Adjacency List + 재귀 CTE
- `parent_id` 외래키로 트리 표현, SQLite **재귀 CTE(WITH RECURSIVE)**로 전체 트리를 한 번에 조회
- Nested Set 대비 삽입/이동이 간단 → WBS의 빈번한 구조 변경에 적합

### WBS 코드 자동생성
- `wbs_code_service.recalculate_codes()`가 항목 추가/이동/삭제 시 전체 코드 재계산 (최상위 `1.0`, 하위 `1.1`, 세부 `1.1.1`)
- `sort_order`(정렬용 정수)와 `wbs_code`(표시용 문자열) 분리 관리. flat 조회는 sort_order, 트리 조회는 wbs_code 기준

### DB 접근 · 마이그레이션
- ORM 없이 `sqlite3` + `Row` 팩토리. `PRAGMA journal_mode=WAL` + `foreign_keys=ON`
- `init_db()`가 `schema_version`으로 적용 이력 추적 → 매 서버 시작 시 미적용 마이그레이션만 안전하게 재실행

### 인증/권한: Flask session + werkzeug
- 쿠키 기반 세션 + werkzeug 비밀번호 해싱. **세션은 브라우저 쿠키 단위**(전역 서버 상태 없음) → 동일 브라우저 2탭은 쿠키를 공유하므로 다중 사용자 테스트는 시크릿 창/다른 브라우저 사용
- **5단계 역할**: **admin**(전역 전권) > **PM**(프로젝트 전권: 수정/삭제/초기화/이력·메일·AI) > **PL**(개발자 + AI + 계획일자 수정) > **developer**(WBS 편집, 단 계획시작/완료 제외) > **viewer**(읽기 전용). 레벨 `{viewer:0, developer:1, pl:2, pm:3, admin:4}`
- **PM/PL은 프로젝트별 역할**: `project_member.role`(pm/pl/developer/viewer)이 판정의 실제 출처. `get_project_role` = admin이면 admin, 아니면 project_member.role. **admin/PM이 프로젝트 수정 화면에서 멤버 추가·삭제 + 역할 지정**(PM은 담당 프로젝트 멤버 관리 전권, PM 승격 포함). update_project는 pm 게이팅이라 도달자(admin/pm)면 멤버 반영
- **전역 역할(`user.role`)은 관리자/일반 2단계**(admin/developer)로 축소 — 시스템 관리자 여부만 구분하고 업무 권한과는 무관. 유저 관리 화면에서 관리자/일반만 지정하며, PM/PL/개발자/뷰어 같은 업무 권한은 프로젝트별로 일원화
- **전역 admin 전용**(프로젝트 목록): 새 프로젝트 생성 · 유저관리 · 백업/복원
- **계획시작/계획완료(plan_start/plan_end)**: pl/pm/admin만 수정. developer는 그리드에서 셀 잠금 + "PM/PL에게 요청하세요" 안내, 백엔드 PATCH/PUT도 403 (batch는 해당 필드 무시)
- `is_active=0` 계정은 로그인 차단. `requires_password_change=1`이면 `base.html`이 모달로 진입 차단 후 새 비밀번호 강제
- **API 토큰 인증**: API 데코레이터는 `Authorization: Bearer <token>`(SHA-256 대조) 또는 세션으로 `g.user` 해석. admin이 유저별 발급(평문은 이메일로만 전달). Claude CLI 등 외부 클라이언트가 세션 없이 동일 권한으로 호출 (§8 2026-06-25 참조)
- 데코레이터: `@login_required`(페이지) / `@api_login_required`(API) / `@project_access_required(min_role)` / `@admin_required`
- **그리드 역할별 UI 게이팅**: WBS CRUD·Gantt·Excel붙여넣기는 developer 이상 / **AI 바는 pl 이상** / **메일 버튼은 pm 이상**(서버도 동일) / 프로젝트 카드 관리버튼(수정·삭제·초기화·이력)은 **admin·pm** / 오늘의 알림 칩은 admin·pm=전체, 그 외=본인 담당만
- 초기 관리자 자동 생성: `yoonsm@daou.co.kr` / `zaq12wsx` (윤순무)

### 실시간 협업 (SSE) — 2026-07-16
- **인메모리 Pub/Sub 브로커** (`app/services/event_broker.py`): 프로젝트별 구독자 큐(`queue.Queue`) 관리. WBS 변경 시 `publish(project_id, event)`로 전파. **단일 프로세스 전제** — 다중 워커 배포 시 Redis Pub/Sub 등으로 교체 필요
- **SSE 엔드포인트** `GET /api/wbs/<pid>/events`: 인증 후 즉시 DB 커넥션 반납(`close_db()`)해 장시간 연결이 커넥션을 붙잡지 않게 함. 25초 하트비트로 죽은 연결/프록시 타임아웃 방지. `X-Accel-Buffering: no`
- **변경 전파**: 모든 쓰기 지점(create/update/patch/delete/move/batch/clear/AI/import)에서 `wbs_changed` 이벤트 발행 (`updated_by` 포함)
- **그리드 자동 갱신** (`grid.js`): `EventSource`로 구독. **본인 변경은 무시**(updated_by === USER_NAME). 셀 편집 중이면 즉시 덮어쓰지 않고 "지금 갱신" 배너 표시 후 편집 종료 시 반영(클로버링 방지)
- **셀 편집 presence**: `POST /editing`(DB 무접근, 브로커로만 전파)로 편집 시작/종료 신호. 다른 사용자가 편집 중인 셀에 **편집자별 색상 외곽선 + 이름 배지** 표시. 6초 하트비트 / 15초 만료 / `pagehide` sendBeacon으로 표시 잔류 방지. `<tr>`에 `data-id`로 재렌더 후에도 복원. 인라인 편집 셀 대상(세부항목/진행상태 팝업·진행률 입력은 제외)

### AI 어시스턴트: 멀티 프로바이더 LLM

`_call_llm()`이 `.env`의 `AI_MODEL`로 분기한다. **SDK import는 전부 함수 안 지연 로딩** — 미사용 프로바이더가 설치되지 않은 환경에서도 무방.

| `AI_MODEL` | 호출 경로 | 필요한 설정 | 파라미터 |
|---|---|---|---|
| `GEMINI` | OpenAI 호환 엔드포인트 (`openai` SDK) | `AI_API_KEY` · `AI_MODEL_NAME` · `AI_BASE_URL`(미설정 시 Google 호환 엔드포인트) | temperature=0, max_tokens=2048 |
| `DAOU_GATEWAY` | 사내 AI Gateway — OpenAI 호환이라 `_call_openai_compatible()` 재사용 | `AI_API_KEY` · `AI_BASE_URL`(기본 `https://dev-llmgw.daouax.com/v1`) · `AI_MODEL_NAME`(기본 `claude-sonnet-5`) | temperature=0, max_tokens=16000, **기능 태그 필수** |
| `CLAUDE` | Anthropic Messages API (`anthropic` SDK) | `AI_API_KEY` · `AI_MODEL_NAME`(기본 `claude-opus-5`) | max_tokens=16000, `effort=medium`, **temperature 금지** |
| `LOCAL` | `claude -p --max-turns 1` subprocess (timeout 120초) | 없음 — 서버 머신에 로그인된 Claude CLI 구독 사용 | 호출당 API 과금 없음. 실측 8~35초 |

**DAOU_GATEWAY 주의점**
- **기능 태그 필수** — 모든 호출에 `metadata.tags`로 **정확히 1개**(`WBS_AI_ASSISTANT`). 누락·빈 리스트·2개 이상은 게이트웨이가 **400**으로 거절. 기능별 사용량·비용 집계 키다
- **반드시 `extra_body`로 전달** — 파이썬 OpenAI SDK는 표준 외 필드를 **조용히 버려** body 최상위에 넣으면 서버까지 가지 않는다 (curl은 반대로 최상위에 넣고 `extra_body`라는 키를 쓰면 안 됨)
- **`temperature=0` 사용 가능** — CLAUDE 직접 호출은 4.7+ 모델에서 400이지만 **게이트웨이 경유 시엔 `claude-sonnet-5`도 정상 수용**(실호출 확인). 프로바이더별 분기 불필요
- **사내 TLS 인터셉션 대응 필수** — 사내망은 자체 루트 CA(`C=KR, O=daou, CN=daou`, 2044-01 만료)로 TLS를 가로챈다. curl은 Windows 인증서 저장소를 써서 통과하지만 **httpx/OpenAI SDK는 certifi 번들만 보므로 `CERTIFICATE_VERIFY_FAILED`** — SDK가 `Connection error.`로 감싸 원인이 드러나지 않는다. `python scripts/make_ca_bundle.py`로 결합 번들을 만들고 `.env`에 `SSL_CERT_FILE=certs/ca-bundle.pem` 지정. `certs/daou-root.pem`(공개 인증서)만 커밋하고 결합본은 gitignore. **certifi 업그레이드 시 번들 재생성 필요**
- **방화벽** — 사내망 로컬 PC는 바로 접근 가능하나 **앱 구동 서버는 별도 결재 필요**(`dev-llmgw.daouax.com` TCP 443). Docker 배포 시엔 이미지에 CA를 넣거나 같은 번들을 마운트해야 한다
- 키 alias `fulfillment-dev` / 허용 모델 그룹 `text-models` / 차단 한도 없음(월 $200 초과 시 알림, 팀 공통 $500 소진 시 429). 모델 목록은 `GET /v1/models`

**CLAUDE 주의점** — Claude 4.7 이후 모델은 **`temperature`/`top_p` 미지원(400)**이라 추론 깊이는 `output_config={"effort": "medium"}`로 조절한다. thinking이 기본 ON이며 `max_tokens`를 함께 소비하므로 여유를 크게(16000) 둔다. `stop_reason == 'refusal'`이면 `content`를 읽지 않고 오류로 변환(안전 분류기 거부 시 빈 배열이라 인덱싱하면 크래시)

**처리 흐름** — `process_command()`가 진입점. 프로젝트 개요 + WBS 요약으로 시스템 프롬프트를 조립해 LLM에 넘기고, 돌아온 JSON의 `action`에 따라 `_execute_query/add/generate/delete/update/move()`를 실행한다. **DB 조작은 전부 서버 코드가 수행**하고 LLM은 자연어→JSON 변환만 담당한다.
- 응답 파싱은 3단계 폴백(json 표시 코드블록 → 임의 코드블록 → `{`~`}` 구간 추출)
- query 결과는 `items`(+`_row_number`·`start_gap_days`·`end_gap_days`)와 `summary`(건수·공수합·평균진행률)를 반환하고, 프론트는 항목 id를 `aiFilterIds`에 담아 그리드를 필터링한다. `insight` 필드가 오면 분석 코멘트로 표시
- 라우트는 `pl` 이상 게이팅 + viewer의 변경성 액션 403 이중 방어. 변경 액션은 SSE로 전파

**분석 대상 축소(입력 토큰 억제)** — `_get_items_summary()`가 전체 행을 나열하지 않고 **①완료(진행률 100) 제외 ②계획기간이 오늘~4주(`_ANALYSIS_WINDOW_DAYS=28`) 창을 벗어난 미래 항목 제외**. 단 **기한 경과 미완료(지연)는 창 밖이어도 포함**(분석의 핵심). 전체 건수·완료 수는 헤더 집계로 남겨 맥락을 유지하고, 프롬프트에 "목록은 전체가 아니다"를 명시해 LLM이 "없다"고 단정하지 않게 한다. query 필터는 `_execute_query`가 전체 데이터로 실행하므로 **조회 정확도는 불변**
- 실측 절감: 345건(완료 139) 프로젝트 35.6K자→14.2K자(**61%**). 단 **지연 항목이 많으면 절감폭이 작다**(173건·완료 18건 프로젝트는 10%) — 지연은 제외 대상이 아니기 때문

**generate 액션**(마일스톤 기반 태스크 일괄 생성) — 프로젝트 `description`의 마일스톤을 근거로 여러 건 생성. 기존 Task가 있으면 `구분`/`Task`/`서브태스크`를 **그대로 복사**하고 새 `세부항목`만 작성한다. 담당자 `AI생성`·공수 `2`·진행률 `0`은 **서버 고정**(LLM 값 무시). 일정은 마일스톤 시기("8월 3주")를 LLM이 날짜로 환산하고, 시기 언급이 없으면 서버가 오늘 기준 영업일로 채운다(`_next_business_day`/`_add_business_days`로 토·일 배제). 한 번에 최대 30건
- **LLM 오류 방어 2중**: ①프롬프트에 기존 Task 재사용 few-shot 예시 + "category에 마일스톤명 금지" 명시 ②서버가 `task_name`/`detail` 빈 항목과 (구분·Task·서브태스크·세부항목) 완전 중복 항목을 스킵(`skipped` 카운트로 반환). 실제로 LOCAL 모델이 category 자리에 마일스톤명을 넣고 task_name을 비우는 실수를 반복해 추가한 장치

**move 액션** — TID(행번호) 기준 순서 이동(`source_row`/`target_row`/`position`). 전역 flat 리스트에서 빼고 대상 위/아래에 삽입한 뒤 `sort_order`를 0..N-1로 재할당하고 WBS 코드를 재계산한다. parent_id는 불변

**동시성 제약** — LOCAL(CLI subprocess)만 순차 처리(120초×N 대기 가능). GEMINI/DAOU_GATEWAY/CLAUDE(HTTP)는 해당 없음. `app.run(threaded=True)`로 단기 완화

**비(非)LLM 부속** — `analyze_schedule_gaps()`는 같은 모듈에 있지만 LLM을 쓰지 않는 순수 계산 함수로, `GET /api/wbs/<pid>/schedule-gaps`가 계획 대비 실제 일정 갭(지연/조기/정시)을 집계할 때 쓴다

### 태스크 갱신 알림 자동 메일 (APScheduler)
- **목적**: 프로젝트별 지정 시각에 담당자에게 이번주 할당 태스크를 메일로 보내 일정·진행률 갱신 유도
- **스케줄러**(`scheduler.py`): `BackgroundScheduler` 1개, **1분 간격 폴링**. `task_notify_enabled=1` 프로젝트의 `task_notify_time`이 지난 평일에 하루 1회 발송. 분 단위 폴링 이유: 프로젝트별 시각 상이 + 런타임 변경
    - **하루 1회 판정은 DB `project.task_notify_last_date`**(발송 완료 또는 건너뜀을 기록). 메모리 기록이던 이전 방식은 **재기동마다 초기화되어 발송시각이 지난 뒤 기동하면 그날 메일을 다시 발송**했다
    - **뒤늦은 발송 차단**: 발송시각을 `_CATCHUP_MINUTES`(120분) 넘겨 처리되는 경우(종일 중단 후 저녁 기동 등)는 보내지 않고 그날 처리 완료로 기록. → 재기동 자체로는 메일이 나가지 않는다
    - 발송 시도 **직전**에 날짜를 기록한다(발송 예외 시 1분마다 재시도 폭주 방지)
    - **단일 프로세스 전제**: waitress 단일 프로세스라 중복 없음. 멀티프로세스 시 외부 스케줄러/락 필요
    - 기동 가드: TESTING·`ENABLE_SCHEDULER=0`·Flask reloader 부모 프로세스에서는 미기동
- **발송**(`notification_service.py`): 이번주 미완료 태스크 → 담당자별 그룹화 → 이메일 조회 → HTML 발송. 0건/이메일 없는 담당자는 미발송
- **링크 URL**: 요청 컨텍스트 없어 `config.APP_BASE_URL`(기본 `http://localhost:5000`) 사용

### 프론트엔드: template/wbs-manage.html 기반
- WBS 그리드는 `wbs.html`(독립 페이지, `wbs.css`). 대시보드(`index.html`)만 `base.html` 상속
- **상단바 구성**: 좌측 제목(프로젝트명 + `Work Breakdown Structure` + 버전 + 가이드 `?` 원형 버튼) / 우측 기능 버튼(대시보드 · Gantt · 통계 · 이력) + **데이터관리 드롭다운**(CSV·Excel 내보내기 / Excel 붙여넣기 · 샘플.xlsx 다운로드) + 구분선 오른쪽 **사용자 영역**(유저명·역할, 로그아웃). 아이콘은 이모지 대신 **인라인 SVG**(`currentColor` stroke, `.btn-top svg`). 드롭다운 토글은 `wbs.html` 인라인 스크립트 `toggleTopMenu()`(바깥 클릭 시 닫힘)
- **셀 선택은 엑셀 방식**(`grid.js` §Cell Selection): 클릭=선택(편집 아님), 드래그·Shift+클릭·Shift+방향키로 사각형 범위, Ctrl+A 전체. 상태는 `cellSel {r1,c1,r2,c2}`(렌더링된 행 위치 + COLUMNS 인덱스, 앵커=r1/c1) → `.cell-selected`/`.cell-active` 클래스로 표시하고 재렌더 후 `applyCellSelection()`으로 복원
- **편집 진입**: 더블클릭 / F2 / Enter / 문자 입력(입력 문자로 대체). 진입 시에만 `contenteditable`을 부여하고 blur 시 제거(300ms debounce → PATCH 자동저장, 앞뒤 trim). Enter=커밋+아래 이동, Tab=커밋+오른쪽 이동, Escape=취소. 세부항목/진행상태는 더블클릭 팝업(개행 지원), 진행률은 더블클릭 입력. 날짜 컬럼 자동 변환(다양한 형식 → yyyy-MM-dd, 그리드는 yy-MM-dd 축약 표시)
- **Delete**=선택 범위 값 비우기(`clearSelectedCells` → 배치 저장, 진행률은 0, developer의 계획시작/완료는 스킵) / **Ctrl+C**=선택 범위를 TSV로 클립보드 복사(탭·개행·따옴표 포함 값은 따옴표 인용 → 엑셀에 그대로 붙여넣기) / **Ctrl+V**=선택 위치부터 붙여넣기(`parseClipboardTable`로 인용 해석, 화면 마지막 행을 넘어가면 새 행 추가)
- 행번호(#) = DB 고유 ID. TID 열 클릭으로 행 복수 선택(클릭/Shift/Ctrl/# 전체) → 일괄 삭제(행 선택 상태의 Delete는 행 삭제). **행 선택과 셀 선택은 배타**. 우클릭 컨텍스트 메뉴(삽입/복제/삭제/행이동 TID)
- 필터: 빠른검색(2입력 AND) · 완료 포함 · 나만의 · 이번주 · 지연 · 계획시작 우선 (체크 상태·컬럼폭 localStorage 프로젝트별 유지)
- 정렬: 헤더 `↕` 버튼(asc/desc), TID 헤더 클릭 시 등록순 리셋. 진행률 색상 바(회색→노랑→파랑→초록)
- SPA 미사용 → 빌드 도구 불필요

## 7. 실행 방법

### 로컬 개발

```bash
.venv\Scripts\activate            # (최초) pip install -r requirements.txt
python run.py                     # http://localhost:5000  (debug=True, 자동 리로드)
```
- 서버 실행 시 `instance/wbs.db` 자동 생성 + 미적용 마이그레이션 자동 적용 + 초기 관리자 시드
- `AI_MODEL=DAOU_GATEWAY`로 쓸 때는 **CA 번들을 먼저 만들어야 한다** (없으면 AI 호출이 `Connection error.`로 실패)
  ```bash
  python scripts/make_ca_bundle.py     # -> certs/ca-bundle.pem
  # .env: SSL_CERT_FILE=certs/ca-bundle.pem
  ```

### Docker 배포 (Coolify)

```bash
docker compose up -d --build         # waitress-serve, 5000 포트, wbs-data 볼륨에 DB 영속
```
- 컨테이너 TZ는 `Asia/Seoul` 고정 (스케줄러 발송시각·이력 시각 일관)
- `FLASK_ENV`/`HOST`/`PORT`/`DATABASE_PATH`는 compose가 덮어쓰고, 나머지는 `.env` → 없으면 `app/config.py` 기본값
- 메일 링크용 `APP_BASE_URL`은 compose에 운영 도메인으로 지정

### 테스트

```bash
python -m pytest -q                  # 128건
```

## 8. 변경 이력 (Changelog)

> 각 항목의 현재 동작 상세는 §6, 스키마는 §4 참조. 아래는 "언제 무엇을 했는가" 요약.

- **2026-08-26** — **사내 AI Gateway 프로바이더 추가**: `AI_MODEL=DAOU_GATEWAY` 신설. OpenAI 호환이라 `_call_openai_compatible()`을 파라미터화(base_url 기본값·모델·max_tokens·temperature·extra_body)해 재사용. 게이트웨이 필수 규칙인 기능 태그 1개(`metadata.tags=["WBS_AI_ASSISTANT"]`)를 `extra_body`로 전달(SDK가 표준 외 필드를 버리므로 필수), max_tokens 16000. 실호출로 규칙 검증(태그 누락 시 400 / 게이트웨이 경유 시 claude 모델도 temperature 수용). 사내 루트 CA로 TLS 인터셉션되어 `certs/daou-root.pem` + `scripts/make_ca_bundle.py` 추가(`SSL_CERT_FILE`). 테스트 125→128건. 겸사겸사 **문서 전반 정리** — handoff: 누락돼 있던 `backup_service`/`api_admin`(백업·복원 API)·`certs`/`scripts`·Docker 파일 반영, 마이그레이션 017 추가, Docker 배포·테스트 실행법 보강, AI 섹션 프로바이더 표로 재구성. **API 권한 오기 5건 정정**(프로젝트 수정·삭제·이력플래그·WBS 초기화·메일발송을 admin/developer로 적어뒀으나 실제는 pm). README: 2026-04-13 상태(권한 3단계, AI·SSE·이력 없음, "tests 미구현")에서 현재 기준으로 전면 갱신하고 스키마·API 전량은 handoff 참조로 위임
- **2026-08-25** — **기동 시 태스크 알림 중복 발송 수정**: 하루 1회 판정을 메모리(`_sent_today`)에서 DB(`project.task_notify_last_date`, 마이그레이션 017)로 이전 — 재기동해도 그날 발송 이력이 유지된다. 발송시각을 120분(`_CATCHUP_MINUTES`) 넘긴 뒤늦은 발송은 생략하고 처리 완료로 기록. 스케줄러 상태 응답 `sent_today` → `done_today`(+`catchup_minutes`). 테스트 121→125건
- **2026-08-25** — **그리드 셀 선택·편집을 엑셀 방식으로 전환**: 상시 `contenteditable` 제거 → 클릭=선택, 더블클릭·F2·Enter·문자 입력=편집. 사각형 범위 선택(드래그/Shift/방향키/Ctrl+A), `Delete`로 선택 범위 값 삭제, `Ctrl+C`로 TSV 복사(엑셀 붙여넣기 호환·인용 처리), 붙여넣기는 선택 위치 기준 + TSV 인용 파서 적용. 행 선택(TID 열)은 종전 동작 유지하며 셀 선택과 배타
- **2026-08-07** — **AI 분석 범위 축소 + 태스크 생성 기능**: ①분석용 요약을 미완료 + (지연 or 향후 4주) 항목으로 제한해 입력 토큰 절감(345건 프로젝트 61%). ②**generate 액션** 신설 — 프로젝트 마일스톤 기준 태스크 일괄 생성(담당자 `AI생성`/공수 2 서버 고정, 마일스톤 시기→영업일 일정 환산, 기존 구분·Task 체계 재사용, 중복·빈 항목 서버 스킵). 프론트 그리드 자동 갱신 + 생성 건수 안내, AI 바 placeholder 문구 갱신. 테스트 112→121건
- **2026-08-07** — **AI 프로바이더 정리(GEMINI + Claude API)**: Anthropic Messages API 프로바이더 추가(`AI_MODEL=CLAUDE`, `anthropic` SDK, 기본 모델 `claude-opus-5`, `effort=medium`, refusal 처리). 경량 모델 전용 대응 경로 삭제 — 압축 요약(`_get_compact_summary`)·축약 프롬프트(`_build_compact_system_prompt`)·`id_slot` 전달 제거로 프롬프트 경로 단일화. Claude CLI(LOCAL)는 유지. 테스트 110→112건
- **2026-08-06** — **그리드 상단바 메뉴 정리**: CSV/Excel 내보내기·Excel 붙여넣기·샘플 다운로드를 '데이터관리' 드롭다운으로 묶고, 유저명·로그아웃을 구분선 오른쪽 그룹으로 분리, 가이드를 제목 옆 원형 `?` 버튼으로 이동(상단 버튼 10개→6개). 이모지 아이콘 → 인라인 SVG 라인 아이콘 교체(아이콘 중복 제거 + 다크 배경 가독성). 워크쓰루 1단계 설명 갱신
- **2026-07-24** — 붙여넣기용 **샘플 Excel 다운로드**(`GET /api/io/sample/excel`, 헤더 + 예시 2행 생성). 브랜딩 문구 `for Claude (via MCP)` → `via AI Agent`(전 템플릿 title·로고 크레딧), 랜딩 날짜 자동변환 설명 문구 수정
- **2026-07-16** — **전역 역할 2단계 정리**: `user.role`을 관리자/일반(admin/developer)으로 축소(016 마이그레이션, 전역 viewer→developer 통일). 업무 권한은 프로젝트별로 일원화 — 유저 관리 화면은 관리자/일반만, PM/PL/개발자/뷰어는 프로젝트 수정 화면에서 지정. 랜딩 권한 체계 소개도 5개 카드로 갱신
- **2026-07-16** — **권한 5단계 확장**: admin > PM > PL > developer > viewer. PM/PL은 프로젝트별 역할(`project_member.role`이 판정 출처로 복귀, 2026-04-30 단일관리 되돌림, 015 마이그레이션). PM=프로젝트 전권(전역 admin 기능 유저관리·백업·새프로젝트 제외), PL=개발자+AI+계획일자 수정, developer=계획시작/완료 수정 불가(프론트 잠금+얼럿, 백엔드 403). 멤버 추가·삭제 및 역할 지정은 프로젝트 수정 화면에서 admin/PM(멤버 관리 전권). API 게이팅(프로젝트 수정/삭제/초기화/이력·메일=pm, AI=pl) + 프론트 게이팅 + 테스트 23건 추가
- **2026-07-16** — **SSE 실시간 협업**: 그리드 실시간 자동 갱신(EventSource, 본인 변경 무시, 편집 중 클로버링 방지 배너) + 셀 편집 presence(편집자 외곽선·이름 배지) + 인메모리 이벤트 브로커. 랜딩 기능카드 'AI 어시스턴트'→'실시간 협업'으로 교체(하단 AI 상세 섹션과 중복 제거). 태그 `v1.0.0`(베이스라인)/`v1.1.0`(SSE 갱신)/`v1.2.0`(presence+랜딩) 부여, origin·gitea 푸시
- **2026-06-25** — Claude CLI 연동: API 토큰 인증(013 마이그레이션, Bearer/세션 통합) + `wbs-report` 스킬. 날짜 하이픈 `yy-mm-dd` 프론트 변환, 빠른검색 AND 추가조건, 퀵서치 필터 localStorage 유지, 계획시작 우선 정렬. 테스트 67→77건
- **2026-06-12** — 그리드 우클릭 "행 이동 TID" 메뉴 (목표 TID 입력 → splice 이동)
- **2026-06-10** — Gantt 담당자 범례 → 클릭형 필터 토글 버튼(`excludedAssignees`), 버전 0.96
- **2026-05-26** — 주간 통계 표 헤더 [?] SVG 툴팁(계산식 명시), 빠른검색 "지연 태스크" 필터
- **2026-05-22** — 프로젝트 공지사항 marquee(012 마이그레이션, 그리드 상단 우→좌 흐름)
- **2026-05-15** — WBS 변경 이력 추적 시스템(010·011 마이그레이션, `wbs_change_history` + 프로젝트별 ON/OFF 플래그 + 이력 모달). AI 어시스턴트 move 액션 추가
- **2026-05-07** — Gantt 일자 정규화 버그 수정(009 마이그레이션 + 백엔드 `_normalize_date`, `YY-MM-DD`→`20YY-MM-DD`). 로고 `logo.png`→`logo2.png`. footer 필터 정보 표시 조건 보강
- **2026-04-30** — 그리드 컬럼 폭 드래그 리사이즈, 정렬 트리거 `↕` 버튼 분리, 알림 지연 판단 KST 보정, 푸터 필터 정보. **권한 user.role 단일관리 전환**(008 마이그레이션, 이전 clamp 정책 대체). 대시보드/통계 진행률 공수 가중 산식 통일(`_round_half_up_1` 사사오입)
- **2026-04-23** — pytest API 테스트 스위트 신설(67건). 프로젝트 설명란 → 개요/마일스톤 기입 유도 + AI 프롬프트에 개요 주입. 주간 통계 진척률 공수 기준 변경. 랜딩 AI 어시스턴트 쇼케이스 섹션
- **2026-04-22** — 패스워드 리셋 강제 변경 플로우(005 마이그레이션, 임시 PW 로그인 시 모달 강제 + 서버 난수 생성·메일 발송)
- **2026-04-17** — 대규모 개선: 주간 통계 지표 재정의, 유저 관리 기능 + 역할 리네이밍(participant→developer, 004 마이그레이션), 그리드 역할별 UI 게이팅, 메인 라우트 `/` 분기 + 랜딩 페이지, 회원가입 비밀번호 확인, 로고·파비콘·브랜드, Gantt 개선(담당자 색상/완료 필터/오늘 세로선/범례), 워크쓰루 투어
- **2026-04-16** — 주간 진척 통계 기능(003 마이그레이션 + 트리거 + 통계 모달 + Chart.js). 지연 태스크 담당자별 메일 알림
- **2026-04-15** — AI 어시스턴트 도입(자연어 → CRUD), AI 입력바 UI, 일정 지연 분석 API, 통계 카운트 버그 3건 수정
- **2026-04-14** — 드래그앤드롭 순서 저장 수정(sort_order 기준), Gantt 한국어 로케일(로컬 번들 패치), 날짜 표시 축약
- **2026-04-13** — 그리드 UX 개선
- **2026-04-10** — 초기 구축: Flask 앱 팩토리, SQLite 스키마(001·002 마이그레이션), 프로젝트/WBS CRUD, 코드 자동생성, 재귀 CTE 트리, CSV/Excel Import·Export, 대시보드, WBS 그리드 UI(template 기반), Gantt 차트, 인증/권한 시스템

## 9. 미구현 / 향후 작업

- [ ] 인쇄/PDF 보고서 출력
- [ ] 대시보드 페이지 차트 (통계 모달 차트는 구현됨)
- [ ] Excel Import UI (파일 업로드 폼)
- [ ] 에러 핸들링 고도화 (전역 에러 핸들러)
- [ ] 멀티 프로세스 확장 — 현재 Docker(waitress 단일 프로세스 8스레드)로 배포 중. **SSE 브로커·스케줄러가 단일 프로세스 전제**라 워커를 늘리려면 Redis Pub/Sub·외부 스케줄러가 선행돼야 함
- [ ] AI 어시스턴트 동시성 (LOCAL/CLI 한정 잔여 이슈. `threaded=True` 단기 개선 적용. 중기: Celery/RQ 작업 큐)
- [ ] 사내 AI Gateway 앱 서버 방화벽 결재 (`dev-llmgw.daouax.com` TCP 443) — 완료 전까지 서버 배포본은 `AI_MODEL=LOCAL` 유지
- [ ] 변경 이력 archival/rotation 정책 (현재 무제한 누적)
- [ ] 유저 삭제 (현재 비활성화로 대체)
- [ ] 셀 편집 presence를 세부항목/진행상태 팝업·진행률 입력까지 확장

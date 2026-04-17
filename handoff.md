# WBS 관리 시스템 - Handoff 문서

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | WBS(Work Breakdown Structure) 관리 시스템 |
| 목적 | 프로젝트의 계층적 작업 분해 구조를 웹에서 생성/관리하는 도구 |
| 저장소 | https://github.com/YoonSoonMoo/wbs.git |
| 작업일 | 2026-04-10 (초기), 2026-04-13 (그리드 UX 개선), 2026-04-14 (버그수정/Gantt 한국어), 2026-04-15 (AI 어시스턴트, UI 개선, 통계 버그수정), 2026-04-16 (주간 진척 통계, 지연 메일 알림), 2026-04-17 (주간 통계 지표 재정의, 유저 관리 기능, 역할 리네이밍, 역할 게이팅, 랜딩/로그인 브랜드, 로고·파비콘, 회원가입 비밀번호 확인) |

## 2. 기술 스택

| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Language | Python | 3.x | |
| Framework | Flask | 3.1.1 | 앱 팩토리 패턴 |
| Database | SQLite | 내장 | `sqlite3` 모듈 직접 사용 (ORM 없음) |
| Frontend | Jinja2 + Vanilla JS | | 서버 렌더링 + AJAX 하이브리드 |
| Font | Noto Sans KR + JetBrains Mono | | Google Fonts CDN |
| Excel | openpyxl | 3.1.5 | Excel Import/Export |
| Gantt | Frappe Gantt | 0.6.1 | 로컬 번들 (한국어 로케일 패치), Gantt 차트 시각화 |
| Chart | Chart.js | 4.4.1 | CDN, 통계 모달 차트 (도넛, 라인) |
| 환경변수 | python-dotenv | 1.1.0 | |
| WSGI | waitress | 3.0.2 | Windows 프로덕션 서버 |
| Test | pytest | 8.3.5 | |

## 3. 디렉토리 구조

```
wbs/
├── app/
│   ├── __init__.py              # Flask 앱 팩토리 (create_app, admin 시드, context_processor)
│   ├── auth.py                  # 인증 데코레이터 (login_required, project_access_required 등)
│   ├── config.py                # 환경설정 (Dev/Prod/Test)
│   ├── extensions.py            # DB 헬퍼 (get_db, close_db, init_db)
│   ├── models/
│   │   ├── project.py           # 프로젝트 CRUD 쿼리
│   │   └── wbs_item.py          # WBS 항목 CRUD 쿼리 (재귀 CTE 트리 조회, _trim 헬퍼)
│   ├── services/
│   │   ├── wbs_service.py       # WBS 핵심 비즈니스 로직 (트리 구축, 이동, 일괄수정)
│   │   ├── wbs_code_service.py  # WBS 코드 자동생성/재계산 로직
│   │   ├── auth_service.py      # 인증 서비스 (register, login, get_project_role 등)
│   │   ├── dashboard_service.py # 대시보드 통계 (카테고리별, 담당자별, 지연업무)
│   │   ├── ai_assistant.py      # AI 어시스턴트 (Claude CLI subprocess, 자연어 → WBS 조회/추가/수정/삭제)
│   │   ├── import_export.py     # CSV/Excel Import/Export
│   │   └── mail_service.py      # 지연 태스크 이메일 알림 (SMTP HTML 메일 발송)
│   ├── routes/
│   │   ├── __init__.py          # 블루프린트 등록 (register_blueprints)
│   │   ├── auth.py              # 인증 라우트 (/login, /register, /logout)
│   │   ├── main.py              # 페이지 라우트 (/=landing 또는 /dashboard 리다이렉트, /dashboard, /project/<id>/wbs, /project/<id>/gantt)
│   │   ├── api_project.py       # 프로젝트 REST API (/api/projects)
│   │   ├── api_wbs.py           # WBS REST API (/api/wbs)
│   │   ├── api_users.py         # 유저 관리 REST API (/api/users, admin 전용)
│   │   └── api_import_export.py # Import/Export API (/api/io)
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css            # 대시보드/랜딩/인증 스타일 (Easy WBS 브랜드 그라디언트 텍스트 포함)
│   │   │   ├── wbs.css              # WBS 그리드 전용 스타일 (template 기반)
│   │   │   └── frappe-gantt.min.css # Frappe Gantt CSS (로컬)
│   │   ├── img/
│   │   │   └── logo.png             # 파비콘 및 WBS 페이지 로고 이미지
│   │   └── js/
│   │       ├── app.js               # API 헬퍼, 토스트 알림, 유틸리티
│   │       ├── grid.js              # WBS 그리드 UI (인라인편집, 확장편집, 복수선택, 날짜파싱, 컨텍스트메뉴)
│   │       ├── gantt.js             # Gantt 차트 (Frappe Gantt 래퍼)
│   │       ├── frappe-gantt.min.js  # Frappe Gantt 라이브러리 (로컬, ko 로케일 패치)
│   │       └── dashboard.js         # 대시보드 (프로젝트 목록, 통계카드, 데이터 초기화)
│   └── templates/
│       ├── base.html            # 기본 레이아웃 (대시보드용, 탑바 로고 이미지, 파비콘 포함)
│       ├── landing.html         # 랜딩 페이지 (비로그인 시 / 경로, Easy WBS 브랜드 + Provided by Claude 배지)
│       ├── login.html           # 로그인 페이지 (Easy WBS 브랜드 텍스트 + 배지, 파비콘)
│       ├── register.html        # 회원가입 페이지 (비밀번호 확인 필드, 실시간 일치 검증)
│       ├── index.html           # 대시보드 페이지 (/dashboard, 프로젝트 목록, 유저 관리 모달)
│       ├── wbs.html             # WBS 그리드 뷰 (독립 페이지, template 기반, 역할별 UI 게이팅)
│       └── gantt.html           # Gantt 차트 뷰 (viewer 접근 차단)
├── migrations/
│   ├── 001_initial.sql          # 초기 DB 스키마 (project, wbs_item 테이블)
│   ├── 002_auth.sql             # 인증 스키마 (user, project_member 테이블)
│   ├── 003_stats.sql            # 통계 스키마 (updated_by, completed_at 컬럼, 완료 트리거)
│   └── 004_user_mgmt.sql        # 유저 관리 (is_active 컬럼, participant → developer 이관)
├── instance/                    # SQLite DB 파일 (자동 생성, gitignore 대상)
├── tests/                       # 테스트 디렉토리 (미구현)
├── template/
│   └── wbs-manage.html          # UI 레퍼런스 원본 (단독 HTML, localStorage 기반)
├── .venv/                       # Python 가상환경
├── requirements.txt             # 의존성 목록
├── run.py                       # 실행 진입점
├── .gitignore                   # Git 무시 파일 목록
└── handoff.md                   # 이 문서
```

## 4. DB 스키마

### project 테이블
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 프로젝트명 |
| description | TEXT | 설명 |
| start_date | TEXT | 시작일 (YYYY-MM-DD) |
| end_date | TEXT | 종료일 |
| created_at | TEXT | 생성일시 |
| updated_at | TEXT | 수정일시 (트리거 자동) |

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
| plan_start | TEXT | 계획 시작일 |
| plan_end | TEXT | 계획 완료일 |
| actual_start | TEXT | 실제 시작일 |
| actual_end | TEXT | 실제 종료일 |
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
| role | TEXT | 전역 역할 (admin/developer/viewer), CHECK 제약 적용 |
| is_active | INTEGER | 활성 여부 (1=활성, 0=비활성). 비활성 계정은 로그인 차단 |
| created_at | TEXT | 생성일시 |

### project_member 테이블 (프로젝트별 권한)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| project_id | INTEGER FK | 프로젝트 |
| user_id | INTEGER FK | 사용자 |
| role | TEXT | 프로젝트 내 역할 (developer/viewer), CHECK 제약 적용 |

- PK: (project_id, user_id) 복합키
- admin 역할 사용자는 project_member 없이도 모든 프로젝트에 접근 가능

### schema_version 테이블 (마이그레이션 버전 추적)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| version | INTEGER PK | 마이그레이션 파일 번호 (001, 002, ...) |
| applied_at | TEXT | 적용 일시 |

### 트리거
- `trg_wbs_completed` — progress가 100으로 변경 시 `completed_at`을 현재 일시로 설정
- `trg_wbs_uncompleted` — progress가 100 미만으로 변경 시 `completed_at`을 NULL로 초기화

### 인덱스
- `idx_wbs_project` — project_id
- `idx_wbs_parent` — parent_id
- `idx_wbs_code` — (project_id, wbs_code)
- `idx_wbs_assignee` — assignee
- `idx_wbs_sort` — (parent_id, sort_order)

## 5. API 엔드포인트

### 인증/페이지 라우트
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/` | 비로그인: 랜딩 페이지 / 로그인: `/dashboard`로 리다이렉트 |
| GET | `/dashboard` | 대시보드 (프로젝트 목록), 로그인 필요 |
| GET | `/project/<id>/wbs` | WBS 그리드 페이지 |
| GET | `/project/<id>/gantt` | Gantt 차트 (viewer는 `/`로 리다이렉트) |
| GET/POST | `/login` | 로그인 페이지 |
| GET/POST | `/register` | 회원가입 페이지 (비밀번호 확인 필드, 4자 이상) |
| GET | `/logout` | 로그아웃 → /login 리다이렉트 |

### 프로젝트 API (`/api/projects`)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/projects` | 프로젝트 목록 |
| POST | `/api/projects` | 프로젝트 생성 |
| GET | `/api/projects/<id>` | 프로젝트 상세 |
| PUT | `/api/projects/<id>` | 프로젝트 수정 |
| DELETE | `/api/projects/<id>` | 프로젝트 삭제 (admin만) |
| GET | `/api/projects/<id>/members` | 프로젝트 멤버 목록 |
| GET | `/api/projects/users` | 전체 사용자 목록 (멤버 할당용) |

### WBS API (`/api/wbs`)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/wbs/<pid>/items` | WBS 항목 목록 (?mode=flat/tree) |
| POST | `/api/wbs/<pid>/items` | 항목 추가 |
| GET | `/api/wbs/items/<id>` | 항목 상세 |
| PUT | `/api/wbs/items/<id>` | 항목 전체 수정 |
| PATCH | `/api/wbs/items/<id>` | 항목 부분 수정 (인라인 편집용) |
| DELETE | `/api/wbs/items/<id>` | 항목 삭제 (자식 포함 재귀 삭제) |
| POST | `/api/wbs/items/<id>/move` | 항목 이동 (parent_id, sort_order) |
| POST | `/api/wbs/<pid>/items/batch` | 일괄 수정 |
| DELETE | `/api/wbs/<pid>/items` | 프로젝트 WBS 전체 초기화 (developer 이상) |
| GET | `/api/wbs/<pid>/stats` | 통계 (전체/완료/진행/지연 건수, 평균 진행률) |
| GET | `/api/wbs/<pid>/delayed` | 지연 업무 목록 |
| GET | `/api/wbs/<pid>/dashboard` | 대시보드 종합 데이터 |
| GET | `/api/wbs/<pid>/schedule-gaps` | 계획일 vs 실제일 차이 분석 (지연일수 포함) |
| GET | `/api/wbs/<pid>/weekly-stats` | 주간 진척 통계 (?weeks=4, 이번 주 + 과거 N주) |
| POST | `/api/wbs/<pid>/send-delay-mail` | 지연 태스크 담당자별 이메일 알림 발송 |
| POST | `/api/wbs/<pid>/ai` | AI 어시스턴트 자연어 질의 처리 |

### 유저 관리 API (`/api/users`, admin 전용)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/users` | 유저 목록 (id, name, email, role, is_active, created_at) |
| PUT | `/api/users/<id>/role` | 권한 변경 — body `{role: "admin\|developer\|viewer"}` |
| POST | `/api/users/<id>/reset-password` | 비밀번호 리셋 — body `{password: "..."}` (4자 이상) |
| PUT | `/api/users/<id>/active` | 활성/비활성 토글 — body `{is_active: 0\|1}` (본인 비활성화 금지) |

### Import/Export API (`/api/io`)
| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/io/<pid>/export/csv` | CSV 다운로드 (UTF-8 BOM) |
| GET | `/api/io/<pid>/export/excel` | Excel 다운로드 (.xlsx) |
| POST | `/api/io/<pid>/import/csv` | CSV 업로드 (multipart/form-data) |
| POST | `/api/io/<pid>/import/paste` | 탭 구분 텍스트 가져오기 |

## 6. 핵심 설계 결정

### 계층 구조: Adjacency List 패턴
- `parent_id` 외래키로 트리 구조를 표현
- SQLite의 **재귀 CTE(WITH RECURSIVE)**로 전체 트리를 한 번의 쿼리로 조회
- Nested Set 대비 삽입/이동이 간단하여 WBS의 빈번한 구조 변경에 적합

### WBS 코드 자동생성
- `wbs_code_service.recalculate_codes()` 함수가 항목 추가/이동/삭제 시 전체 코드 재계산
- 최상위: `1.0`, `2.0` / 하위: `1.1`, `1.2` / 세부: `1.1.1`, `1.1.2`
- `sort_order`는 정렬용 정수, `wbs_code`는 표시용 문자열 → 분리 관리
- 그리드 flat 조회 시 `sort_order` 기준 정렬 (`get_flat_items`), 트리 조회 시 `wbs_code` 기준

### DB 접근: sqlite3 직접 사용
- ORM 없이 `sqlite3` 내장 모듈 + `Row` 팩토리로 dict-like 접근
- `PRAGMA journal_mode=WAL` (동시 읽기 성능) + `PRAGMA foreign_keys=ON` (참조 무결성)
- `updated_at` 트리거로 자동 갱신

### 버전드 마이그레이션 시스템
- `extensions.py`의 `init_db()`가 `schema_version` 테이블로 적용된 마이그레이션을 추적
- `migrations/` 디렉토리에서 `NNN_*.sql` 파일을 버전 순으로 실행, 이미 적용된 버전은 건너뜀
- `ALTER TABLE ADD COLUMN` 중복 실행 에러 방지 (매 서버 시작 시 안전하게 재실행 가능)

### 인증/권한: Flask session + werkzeug
- 외부 라이브러리 추가 없음 (werkzeug는 Flask 내장)
- `flask.session` 쿠키 기반 세션으로 로그인 상태 관리
- `werkzeug.security.generate_password_hash` / `check_password_hash`로 비밀번호 해싱
- 3단계 역할: **admin** (전역 모든 권한) / **developer** (프로젝트 내 읽기/쓰기) / **viewer** (프로젝트 내 읽기 전용)
- admin은 `project_member` 없이도 모든 프로젝트에 접근 가능
- developer/viewer는 `project_member`에 등록된 프로젝트만 접근 가능
- `is_active=0` 계정은 자격 증명이 맞아도 로그인 차단 (`login_user`가 `_inactive` 플래그 반환 → 라우트가 플래시 메시지 표시)
- 역할 레벨: `{'viewer': 0, 'developer': 1, 'admin': 2}` (`auth.py` `project_access_required` 비교 기준)
- **전역 권한이 프로젝트 권한의 상한**: `get_project_role`은 `project_member.role`이 높아도 `user.role`을 초과할 수 없도록 clamp. 예) 전역 viewer가 `project_member.role='developer'`로 등록돼도 effective=`viewer`. 의도는 "관리자가 project_member를 잘못 설정해도 global role이 안전망" 역할
- **그리드 역할별 UI 게이팅 (admin / developer / viewer)**:
    - 그리드 CRUD (추가·수정·삭제·드래그·붙여넣기): admin ✓ / developer ✓ / viewer ✗
    - Gantt 링크: admin ✓ / developer ✓ / viewer ✗ (서버: `/project/<id>/gantt`도 viewer → `/` 리다이렉트)
    - Excel 붙여넣기 (모달 + 직접 paste): admin ✓ / developer ✓ / viewer ✗
    - AI Assistant 바: admin ✓만, developer·viewer 숨김 (서버 `POST /api/wbs/<pid>/ai`도 admin 필요)
    - 메일 전송 버튼: admin ✓만 (서버 `POST /api/wbs/<pid>/send-delay-mail`도 admin 필요)
    - 오늘의 알림(지연 칩): admin=전체 / developer·viewer=본인 담당(`assignee === USER_NAME`)만
- 서버 최초 실행 시 기본 관리자 자동 생성: `yoonsm@daou.co.kr` / `zaq12wsx` (이름: 윤순무)
- 데코레이터 패턴: `@login_required` (페이지), `@api_login_required` (API), `@project_access_required(min_role)`, `@admin_required`
- 프론트엔드: viewer일 때 편집 버튼 숨김 + contenteditable 비활성화 + 컨텍스트메뉴 차단 + API 403 응답 처리

### AI 어시스턴트: Claude CLI subprocess 방식

- `app/services/ai_assistant.py`의 `_call_claude()`가 `claude -p --max-turns 1` subprocess를 **동기 호출** (timeout=120초)
- `process_command(project_id, query)` 진입점: 자연어 질의를 분석해 `_execute_query/add/delete/update()` 중 하나 선택 실행
- 조회 결과는 `ids` 배열과 `display` 문자열로 반환 → 프론트엔드에서 해당 행만 그리드에 필터 표시
- `analyze_schedule_gaps(project_id)`: 계획일 vs 실제 작업일 차이 분석 (지연일수, 공수 집계)
- **동시성 제약**: Flask 개발 서버 단일 스레드 기준, 복수 사용자 동시 질의 시 Claude CLI 호출이 순차 처리됨 (최대 120초 × N 대기 가능). 개선 시 `threaded=True` 또는 Claude API 직접 호출(anthropic SDK) 전환 필요

### 프론트엔드: template/wbs-manage.html 기반 재구성
- WBS 그리드 UI는 `template/wbs-manage.html`의 디자인/동작을 그대로 재현
- `wbs.html`은 `base.html`을 상속하지 않는 독립 페이지 (전용 `wbs.css` 사용)
- 대시보드(`index.html`)는 `base.html` 상속 (별도 디자인)
- 일반 셀은 `contenteditable` 기반 인라인 편집, 세부항목/진행상태는 더블클릭 팝업 편집 (개행 지원)
- 인라인 편집 시 300ms debounce 적용 → PATCH API 자동 저장
- 입력값 앞뒤 공백 자동 trim (프론트 focusout + 백엔드 모델 양쪽)
- 날짜 컬럼 자동 변환: 다양한 형식 → yyyy-MM-dd (focusout, 붙여넣기 시 적용)
- 행번호 클릭으로 복수 행 선택 (Shift 범위, Ctrl 토글, # 전체선택) → 일괄 삭제
- SPA 프레임워크 미사용 → 빌드 도구 불필요, 즉시 개발 가능

### WBS 그리드 UI 상세 (template 호환)
- **레이아웃**: `top-bar → alert-section → AI 입력바 → toolbar → grid → footer-bar`
- **컬럼**: `# | 구분 | Task | 서브태스크 | 세부항목 | 담당자 | 계획시작 | 계획완료 | 실제시작 | 실제종료 | 공수 | 진행률 | 진행상태`
- **행번호(#)**: 화면 순번이 아닌 DB 고유 ID (`item.id`) 표시
- **알림 섹션**: 계획완료일 경과 + 진행률 100% 미만인 항목을 칩으로 표시 (지연일수 + 담당자 포함, 세부항목명 12자 초과 시 `...` 처리)
- **AI 어시스턴트 입력바**: 알림 섹션 아래, 자연어 질의 입력 → 조회/추가/삭제/수정 지원, 조회 결과는 그리드에 필터 적용
- **필터**: 빠른검색(전체 컬럼 검색), 완료 포함(체크박스), 나만의 태스크(체크박스), 담당자(드롭다운)
- **정렬**: 컬럼 헤더 클릭 시 오름차순/내림차순 토글
- **컨텍스트 메뉴**: 우클릭으로 행 삽입(위/아래), 행 복제, 행 삭제 / 복수 선택 시 선택 행 삭제
- **행 복수 선택**: 행번호(#) 클릭 토글, Shift+클릭 범위, Ctrl+클릭 개별, 헤더 # 전체선택/해제 → 툴바 "선택 삭제" 버튼 / Delete 키
- **Excel 붙여넣기**: 셀에서 직접 붙여넣기(멀티셀 자동 감지) + 전용 모달
- **날짜 자동 변환**: `2026/4/12`, `26.4.12`, `04.12`, `4월12일` 등 → `yyyy-MM-dd` (focusout, 붙여넣기 시)
- **세부항목/진행상태**: 더블클릭 팝업 편집 (textarea), 개행 지원, 그리드에 `pre-wrap`으로 줄바꿈 표시
- **진행률 바**: 비율에 따라 색상 변경 (회색→노랑→파랑→초록)
- **풋터**: 총 행 수, 마지막 저장 시각, DB 연결 상태

## 7. 실행 방법

```bash
# 1. 가상환경 활성화
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# 2. 의존성 설치 (최초 1회)
pip install -r requirements.txt

# 3. 서버 실행
python run.py

# 4. 브라우저 접속
# http://localhost:5000
```

- 서버 실행 시 `instance/wbs.db` 파일이 자동 생성됨
- `migrations/001_initial.sql` 스키마가 자동 적용됨

## 8. 구현 완료 항목

- [x] Flask 앱 팩토리 + 환경설정 구조
- [x] SQLite DB 스키마 (테이블, 인덱스, 트리거)
- [x] DB 자동 초기화 (서버 시작 시 마이그레이션 실행)
- [x] 프로젝트 CRUD (모델 + API)
- [x] WBS 항목 CRUD (모델 + 서비스 + API)
- [x] WBS 코드 자동생성/재계산
- [x] 재귀 CTE 기반 트리 조회
- [x] 항목 이동 (부모 변경, 순서 변경)
- [x] 일괄 수정 API
- [x] 대시보드 통계 (전체/완료/진행/지연, 카테고리별, 담당자별)
- [x] CSV Export (UTF-8 BOM)
- [x] Excel Export (openpyxl, 헤더 서식 포함)
- [x] CSV Import / 붙여넣기 Import
- [x] 대시보드 UI (프로젝트 카드, 진행률 바, 생성/수정/삭제)
- [x] WBS 그리드 UI — template/wbs-manage.html 기반 재구성 완료:
  - [x] 레이아웃: top-bar → alert-section → toolbar → grid → footer-bar
  - [x] contenteditable 기반 인라인 편집 (일반 셀)
  - [x] 세부항목/진행상태 더블클릭 팝업 편집 (textarea, 개행 지원, viewer는 readonly)
  - [x] 개행 내용 그리드 표시 (white-space: pre-wrap, 행 높이 자동 확장)
  - [x] 지연 업무 알림 섹션 (칩 + 지연일수)
  - [x] 검색/필터 (진행률, 담당자 드롭다운)
  - [x] 컬럼 헤더 클릭 정렬
  - [x] 우클릭 컨텍스트 메뉴 (행 삽입/복제/삭제/선택행 삭제)
  - [x] 행번호 복수 선택 (클릭 토글, Shift 범위, Ctrl 개별, # 전체) + 일괄 삭제
  - [x] Excel 붙여넣기 (셀 직접 + 전용 모달)
  - [x] 날짜 자동 변환 — 다양한 형식 → yyyy-MM-dd (2026/4/12, 26.4.12, 04.12, 26년4월12일, 4월12일)
  - [x] 날짜 표시 축약 — 그리드에서 yy-MM-dd 형식으로 표시 (shortDate), 편집 시 원본 yyyy-MM-dd 복원
  - [x] 셀 입력값 앞뒤 trim (프론트 focusout + 백엔드 모델 _trim 헬퍼)
  - [x] 진행률 색상 바 (회색→노랑→파랑→초록)
  - [x] 전용 CSS (wbs.css, Noto Sans KR + JetBrains Mono)
- [x] Gantt 차트 뷰 (Frappe Gantt, 주간/월간/분기 보기, 한국어 월 표시)
- [x] API 동작 검증 완료 (프로젝트 생성, WBS 항목 CRUD, 계층 코드 자동생성)
- [x] 인증/권한 시스템:
  - [x] user 테이블 + project_member 테이블 (002_auth.sql)
  - [x] 로그인/회원가입/로그아웃 페이지 (/login, /register, /logout)
  - [x] 비밀번호 해싱 (werkzeug)
  - [x] 세션 기반 인증 (flask.session)
  - [x] 역할 기반 권한: admin / participant / viewer
  - [x] 인증 데코레이터 (login_required, api_login_required, project_access_required, admin_required)
  - [x] 모든 페이지/API에 인증 적용 (미인증 시 /login 리다이렉트 또는 401)
  - [x] admin: 프로젝트 생성/수정/삭제, 멤버 추가/삭제
  - [x] participant: 프로젝트 내 WBS 항목 추가/수정/삭제
  - [x] viewer: 읽기 전용 (편집 버튼 숨김, contenteditable 비활성화, API 403)
  - [x] 프로젝트 생성/수정 시 멤버 할당 UI (참여자/뷰어 역할 선택)
  - [x] 대시보드: admin만 프로젝트 생성/수정/데이터 초기화/삭제 버튼 표시
  - [x] 데이터 초기화 버튼: 프로젝트 목록에서 프로젝트별 WBS 전체 삭제 (DELETE /api/wbs/<pid>/items)
  - [x] 초기 관리자 자동 생성 (yoonsm@daou.co.kr / zaq12wsx)
  - [x] 권한 동작 검증 완료 (admin 로그인, viewer 403 제한)
- [x] 네비게이션 UI 개선:
  - [x] 대시보드(프로젝트 리스트) 페이지: topbar에서 "대시보드" 메뉴 삭제
  - [x] WBS 페이지 top-bar: "WBS" 문자를 프로젝트명으로 대체 (예: 택배허브 시스템 구축)
  - [x] WBS 페이지 top-bar: 로그인 유저 옆에 "📋 대시보드" 버튼 추가 (대시보드로 이동)
  - [x] Gantt 페이지: topbar에 프로젝트명 표시 (WBS와 동일)
- [x] 버그수정 및 개선 (2026-04-14):
  - [x] 드래그앤드롭 순서 저장 수정 — get_flat_list가 sort_order 기준 정렬하도록 변경 (기존 wbs_code 텍스트 정렬 → sort_order)
  - [x] 행 삽입/복제 후 saveSortOrder() 호출 추가 — 삽입 위치가 리로드 후에도 유지
  - [x] Gantt 차트 에러 수정 — frappe-gantt 0.6.1에 한국어 로케일 미포함으로 language:'ko' 사용 시 에러 발생, 로컬 번들에 ko 로케일 패치
  - [x] Gantt 차트 한국어 월 표시 — CDN → 로컬 전환, 1월~12월 한국어 표기
  - [x] 날짜 컬럼 폭 확장 — 71px → 73px (4개 날짜 컬럼)
  - [x] 날짜 표시 축약 — yyyy-MM-dd → yy-MM-dd 표시 (DB 저장은 yyyy-MM-dd 유지)
  - [x] openpyxl 미설치 해결 — Excel 다운로드 ModuleNotFoundError 수정
- [x] AI 어시스턴트 및 UI 개선 (2026-04-15):
  - [x] AI 어시스턴트 도입 — `app/services/ai_assistant.py` (Claude CLI subprocess, 자연어 → 조회/추가/수정/삭제)
  - [x] AI 입력바 UI — 알림 섹션 아래, "AI Assistant" 레이블, Enter 전송, 결과 그리드 필터 연동
  - [x] AI 조회 결과를 그리드에 반영 — 해당 항목 ID만 필터링하여 화면 표시
  - [x] 일정 지연 분석 API 추가 — `/api/wbs/<pid>/schedule-gaps` (계획일 vs 실제일 차이, 지연일수·공수 집계)
  - [x] 지연 판단 로직 개선 — 실제종료일 미기입 시 미완료로 판단 (현재일 - 계획완료일로 계산)
  - [x] AI 결과 시인성 개선 — 상태 이모지, 섹션 구분 표시 (심플 버전)
  - [x] 툴바 UI 개선 — "빠른검색" 레이블 추가, 검색창 폭 확장, "완료 포함" 체크박스, "나만의 태스크" 체크박스, "행 추가" 버튼 위치 이동
  - [x] "AI Assistant" 문구 변경 — AI 바 레이블 텍스트 통일
  - [x] 오늘의 알림 개선 — 세부항목명 12자 초과 시 `...` 처리, 담당자명 칩에 함께 표시
  - [x] 행번호(#) → 고유 ID 표시 — 화면 순번 대신 DB `item.id` 표시로 항목 식별 명확화
  - [x] 통계 카운트 버그 수정 — 세 가지 버그 수정:
    - 완료 카운트: "완료 포함" 미체크 시 항상 0이 되던 문제 → 전체 data 기준으로 계산
    - 지연 카운트: status 텍스트('지연' 포함 여부) 기준 → plan_end < 오늘 날짜 기준으로 통일 (행 하이라이트와 일치)
    - 진행/지연 중복: 지연된 항목이 진행 카운트에도 포함되던 문제 → 지연이면 지연만, 진행이면 진행만 카운트

- [x] 주간 진척 통계 기능 (2026-04-16):
  - [x] DB 마이그레이션 003_stats.sql — `updated_by` TEXT, `completed_at` TEXT 컬럼 추가
  - [x] SQLite 트리거 — progress=100 시 `completed_at` 자동 설정, 100 미만 시 NULL 초기화
  - [x] 버전드 마이그레이션 시스템 — `schema_version` 테이블로 적용 이력 관리, 중복 실행 방지
  - [x] `wbs_service.get_weekly_stats()` — 주차별(월~일) 진척 통계 (이번 주 "진행중" + 과거 N주)
    - 주차 라벨: 금요일 기준 월/주차 (예: 4월 3주차), `week_num = (friday.day - 1) // 7 + 1`
    - 누적 집계 기준: 이번 주=오늘, 과거 주=금요일
    - 신규 태스크: `created_at` 기준, 완료 태스크: `completed_at` (fallback `updated_at`) 기준
    - 전주 대비 delta 계산 (전체/완료/진척률/공수)
    - 현재(라이브) overview: 오늘 기준 전체 집계 + 전주 대비 delta
    - 담당자별 현황: 태스크 수, 공수 합, 완료 수
  - [x] API 엔드포인트 — `GET /api/wbs/<pid>/weekly-stats?weeks=4`
  - [x] 통계 모달 UI — WBS 페이지 top-bar "📊 통계" 버튼, 모달 오버레이로 표시
  - [x] KPI 카드 6개 — 전체 태스크, 완료 태스크, 전체 공수(d), 완료 공수(d), 현재 진척률, 주간 진척률
    - 전주 대비 delta 뱃지 (+초록, -빨강, 0회색)
    - 주간 진척률은 전주 대비 변동분 (+/-%) 별도 카드로 표시
  - [x] 주차별 진척 현황 테이블 — 이번 주(진행중) + 과거 4주, 5컬럼:
    - 주차 | 전체(+신규) | 완료(주간/누적) | 진척률 | 공수(총/완료)
  - [x] 담당자별 현황 3-card 그리드 (template/wbs-stats-light.html 기반):
    - 담당자별 태스크 수 (가로 바 차트)
    - 담당자별 공수 합 d (가로 바 차트)
    - 태스크 / 공수 비중 (Chart.js 도넛 차트 + 범례)
  - [x] 주간 진척률 추이 라인 차트 (Chart.js):
    - 진척률 % (좌축, 영역 채움), 완료 공수 d (우축, 점선), 전체 공수 d (우축, 점선)
  - [x] 차트 메모리 관리 — 모달 닫기/재오픈 시 Chart.js 인스턴스 destroy 처리
  - [x] `update_item()`, `batch_update()` — `updated_by` 파라미터 추가 (session user_name 전달)
- [x] 지연 태스크 메일 알림 (2026-04-16):
  - [x] `mail_service.py` — SMTP HTML 메일 발송 (`build_delay_mail_html`, `send_html_mail`)
  - [x] API 엔드포인트 — `POST /api/wbs/<pid>/send-delay-mail`
  - [x] 담당자별 그룹화 → user 테이블에서 이메일 조회 → 개별 발송
  - [x] 알림 섹션 "📧 메일 전송" 버튼 (지연 태스크 존재 시 표시)

- [x] 주간 진척 통계 지표 재정의 (2026-04-17):
  - [x] 프로토타입 주간 표의 "진척률" 컬럼 프로그레스바 제거, % 텍스트만 표시 (`template/wbs-stats-light.html`)
  - [x] 담당자별 바 차트 "완료/전체" 비율 시각화 — 2중 레이어 바 (전체=투명 22%, 완료=진한 색), 라벨 `완료/전체 · 완료율%` 형식. `template/wbs-stats-light.html`, `app/static/js/grid.js`, `app/static/css/wbs.css` 반영
  - [x] `wbs_service.get_weekly_stats()` 담당자별 쿼리에 `completed_effort` 추가 — 프론트에서 공수 바의 완료분 계산에 사용
  - [x] 주간완료/진척률 재정의 — `completed_week`는 `plan_end`와 `actual_end`가 모두 해당 주 범위 안에 있는 태스크 수. `planned_week` = plan_end가 해당 주 범위 안. `progress_rate = completed_week / planned_week * 100`
  - [x] 프론트 주간완료 셀 `완료 / 예정` 포맷 표시 (예: `8 / 12`)
  - [x] 누적완료 재정의 — `cumulative_completed_week` 필드: 관측 구간의 가장 오래된 주부터 `completed_week`의 러닝 합. 프론트 누적완료 컬럼이 이 값을 사용
  - [x] 상단 KPI 라벨 정리 — "현재 진척률" → "전체 진척률" (누적), "주간 진척률" → "주간 진척률(현재)" (진행중 주차 `weekly[0].progress_rate`)
  - [x] 주차별 표 증감 표시 정리 — 전체·주간완료·완료공수 옆의 델타(+N) 제거
  - [x] 그리드 컨텍스트 메뉴 뷰포트 하단·우측 오버플로 보정 — `showContext()`가 메뉴를 화면 밖에서 측정 후 boundary 초과 시 `pad`만큼 떨어진 위치로 보정 (`app/static/js/grid.js`)

- [x] 유저 관리 기능 + 역할 리네이밍 (2026-04-17):
  - [x] 마이그레이션 `004_user_mgmt.sql` — `is_active` 컬럼 추가 (DEFAULT 1, NOT NULL), `role` CHECK 제약 `admin/developer/viewer`로 갱신, 기존 `participant` 데이터를 `developer`로 이관. SQLite CHECK 변경을 위해 `user`·`project_member` 테이블 재생성 (FK는 `PRAGMA foreign_keys=OFF`로 우회)
  - [x] `auth_service.py` 함수 추가 — `update_user_role`, `reset_user_password`, `set_user_active`. `login_user`는 `is_active=0` 계정에 `{_inactive: True}` 반환
  - [x] `auth.py` role_level participant → developer
  - [x] 새 블루프린트 `api_users_bp` — `/api/users` 하위 4개 엔드포인트 모두 `@admin_required`. 본인 비활성화 시도는 400
  - [x] 템플릿 컨텍스트 `user_id` 추가 (`app/__init__.py` `inject_user`) — 프론트의 본인 식별용
  - [x] 프로젝트 목록 페이지 "유저 관리" 버튼 (admin 전용) + 모달 — 폭 1040px, sticky 헤더, 활성/비활성 뱃지, 권한 셀렉트, PW 리셋/활성 토글 버튼
  - [x] `dashboard.js` 유저 관리 로직 — `loadUserMgmtList`, `changeUserRole`, `resetUserPw`, `toggleUserActive`. 헤더에 "전체 N명 · 활성 N명 · 비활성 N명" 카운트 표시
  - [x] 유저 관리 모달 CSS — `app/static/css/style.css`의 `.user-mgmt-modal`/`.user-mgmt-tbl`/`.user-role-sel`/`.user-badge`/`.user-action-btns` (이름 `white-space:nowrap`, hover, danger 버튼 variant 등)
  - [x] `'participant'` 문자열 일괄 교체 → `'developer'` (`app/routes/api_wbs.py`, `app/routes/api_import_export.py`, `app/static/js/dashboard.js` 멤버 드롭다운. UI 라벨 "참여자" → "개발자")
  - [x] 전체 유저 패스워드 일괄 `local8707!`로 초기화 (백업: `instance/wbs.db.bak-20260417-133255`)

- [x] 그리드 역할별 UI 게이팅 + 권한 clamp 버그 수정 (2026-04-17):
  - [x] `wbs.html` 템플릿 게이팅 — Gantt 링크/AI 바/메일 버튼을 `{% if project_role == 'admin' %}`로 감쌈. Excel 붙여넣기는 기존 viewer 차단 유지
  - [x] `grid.js` 로직 — `updateAlerts()`가 비-admin에게 본인 담당 태스크만 필터(`r.assignee === USER_NAME`). `sendDelayMail()`·`sendAiQuery()` admin 외 토스트 후 조기 리턴. paste 리스너 viewer 조기 리턴
  - [x] 서버 방어 — `send-delay-mail` 및 `/ai` 엔드포인트 `project_access_required('admin')`로 상향. `main.py gantt_view`에서 viewer 요청 시 `/`로 리다이렉트
  - [x] **권한 clamp 버그 수정** — `get_project_role`이 전역 권한을 상한으로 clamp하도록 변경. 이전에는 `project_member.role`이 전역 권한을 초과하면 viewer 유저가 editor 권한을 갖게 되던 문제(`project_member.role='developer'`로 할당된 전역 viewer가 그리드 CRUD 가능) 해결

- [x] 메인 라우트 구조 변경 + 랜딩 페이지 추가 (2026-04-17):
  - [x] `/` 경로 분기 — 비로그인: `landing.html` 렌더 / 로그인: `/dashboard`로 리다이렉트
  - [x] `/dashboard` 라우트 분리 — 기존 `index.html`을 여기로 이전
  - [x] `landing.html` — 히어로·Features·Workflow·권한·기술 스택·푸터 섹션, Chart.js/Gantt/AI Assistant 강조
  - [x] Features 섹션 헤드라인 교체 — "현업에서 필요한 모든 기능" → "계획은 바뀌어도, WBS는 흔들리지 않게" (프로젝트 변수에 유연 대응하는 강점 강조)

- [x] 회원가입 비밀번호 확인 필드 (2026-04-17):
  - [x] `register.html` — `password_confirm` 입력 추가. 실시간 일치 메시지(`✓ 일치 / ✗ 불일치`) + 제출 시 JS 가드
  - [x] `auth.py register()` — 불일치·4자 미만·누락 각각 플래시. 검증 통과 시에만 `register_user()` 호출
  - [x] CSS `.pw-match-msg` / `.ok` / `.err` 추가

- [x] 로고 및 파비콘, 브랜드 스타일 (2026-04-17):
  - [x] `app/static/img/logo.png` 추가. 모든 템플릿 `<head>`에 `<link rel="icon" type="image/png">` 적용
  - [x] 탑바 로고 이미지화 (`base.html`, `.logo-img` height 30px)
  - [x] 랜딩 페이지 로고 이미지 삭제 → "Easy WBS" 그라디언트 텍스트(`.landing-logo-brand` 34px 헤더/26px 푸터, 파랑→보라→밝은파랑 그라디언트) + "Provided by Claude" pill 배지(`.landing-logo-credit` monospace, uppercase, letter-spacing)
  - [x] 로그인 페이지 로고 이미지 삭제 → 랜딩과 동일 브랜드 텍스트 + 배지 (`auth-brand` 컨테이너, 30px)
  - [x] 회원가입 페이지는 기존 로고 이미지 유지(필요 시 동일 교체 대기)

## 9. 미구현 / 향후 작업

- [ ] 테스트 코드 작성 (`tests/`)
- [ ] 변경 이력 추적
- [ ] 인쇄/PDF 보고서 출력
- [x] Chart.js 통계 모달 차트 (도넛, 라인) — 대시보드 페이지 차트는 미구현
- [ ] Excel Import UI (파일 업로드 폼)
- [ ] 에러 핸들링 고도화 (전역 에러 핸들러)
- [ ] 프로덕션 배포 설정 (waitress/gunicorn)
- [ ] 본인 비밀번호 변경 기능 (관리자 리셋은 구현 완료, 사용자 셀프 변경은 미구현)
- [x] 관리자 사용자 관리 UI (역할 변경, 패스워드 리셋, 활성/비활성 토글) — 2026-04-17 완료. 유저 삭제는 미구현(비활성화로 대체)
- [ ] AI 어시스턴트 동시성 개선 — 현재 Claude CLI subprocess 동기 호출로 복수 사용자 동시 질의 시 순차 처리됨. 개선 방향: `threaded=True` (단기), Celery/RQ 작업 큐 (중기), anthropic SDK 직접 호출 (장기 권장)

# WBS 관리 시스템 - Handoff 문서

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | WBS(Work Breakdown Structure) 관리 시스템 |
| 목적 | 프로젝트의 계층적 작업 분해 구조를 웹에서 생성/관리하는 도구 |
| 저장소 | https://github.com/YoonSoonMoo/wbs.git |
| 작업일 | 2026-04-10 (초기), 2026-04-13 (그리드 UX 개선), 2026-04-14 (버그수정/Gantt 한국어) |

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
│   │   └── import_export.py     # CSV/Excel Import/Export
│   ├── routes/
│   │   ├── __init__.py          # 블루프린트 등록 (register_blueprints)
│   │   ├── auth.py              # 인증 라우트 (/login, /register, /logout)
│   │   ├── main.py              # 페이지 라우트 (/, /project/<id>/wbs, /gantt)
│   │   ├── api_project.py       # 프로젝트 REST API (/api/projects)
│   │   ├── api_wbs.py           # WBS REST API (/api/wbs)
│   │   └── api_import_export.py # Import/Export API (/api/io)
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css            # 대시보드 스타일
│   │   │   ├── wbs.css              # WBS 그리드 전용 스타일 (template 기반)
│   │   │   └── frappe-gantt.min.css # Frappe Gantt CSS (로컬)
│   │   └── js/
│   │       ├── app.js               # API 헬퍼, 토스트 알림, 유틸리티
│   │       ├── grid.js              # WBS 그리드 UI (인라인편집, 확장편집, 복수선택, 날짜파싱, 컨텍스트메뉴)
│   │       ├── gantt.js             # Gantt 차트 (Frappe Gantt 래퍼)
│   │       ├── frappe-gantt.min.js  # Frappe Gantt 라이브러리 (로컬, ko 로케일 패치)
│   │       └── dashboard.js         # 대시보드 (프로젝트 목록, 통계카드, 데이터 초기화)
│   └── templates/
│       ├── base.html            # 기본 레이아웃 (대시보드용, 사용자명/로그아웃 표시)
│       ├── login.html           # 로그인 페이지
│       ├── register.html        # 회원가입 페이지
│       ├── index.html           # 대시보드 페이지 (프로젝트 목록/생성, 멤버 할당 UI)
│       ├── wbs.html             # WBS 그리드 뷰 (독립 페이지, template 기반, viewer 제한)
│       └── gantt.html           # Gantt 차트 뷰
├── migrations/
│   ├── 001_initial.sql          # 초기 DB 스키마 (project, wbs_item 테이블)
│   └── 002_auth.sql             # 인증 스키마 (user, project_member 테이블)
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

### user 테이블 (인증)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 이름 |
| email | TEXT UNIQUE | 이메일 (로그인 ID) |
| password_hash | TEXT NOT NULL | 비밀번호 해시 (werkzeug) |
| role | TEXT | 전역 역할 (admin/participant/viewer) |
| created_at | TEXT | 생성일시 |

### project_member 테이블 (프로젝트별 권한)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| project_id | INTEGER FK | 프로젝트 |
| user_id | INTEGER FK | 사용자 |
| role | TEXT | 프로젝트 내 역할 (participant/viewer) |

- PK: (project_id, user_id) 복합키
- admin 역할 사용자는 project_member 없이도 모든 프로젝트에 접근 가능

### 인덱스
- `idx_wbs_project` — project_id
- `idx_wbs_parent` — parent_id
- `idx_wbs_code` — (project_id, wbs_code)
- `idx_wbs_assignee` — assignee
- `idx_wbs_sort` — (parent_id, sort_order)

## 5. API 엔드포인트

### 인증 (페이지 라우트)
| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/login` | 로그인 페이지 |
| GET/POST | `/register` | 회원가입 페이지 |
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
| DELETE | `/api/wbs/<pid>/items` | 프로젝트 WBS 전체 초기화 (participant 이상) |
| GET | `/api/wbs/<pid>/stats` | 통계 (전체/완료/진행/지연 건수, 평균 진행률) |
| GET | `/api/wbs/<pid>/delayed` | 지연 업무 목록 |
| GET | `/api/wbs/<pid>/dashboard` | 대시보드 종합 데이터 |

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

### 인증/권한: Flask session + werkzeug
- 외부 라이브러리 추가 없음 (werkzeug는 Flask 내장)
- `flask.session` 쿠키 기반 세션으로 로그인 상태 관리
- `werkzeug.security.generate_password_hash` / `check_password_hash`로 비밀번호 해싱
- 3단계 역할: **admin** (전역 모든 권한) / **participant** (프로젝트 내 읽기/쓰기) / **viewer** (프로젝트 내 읽기 전용)
- admin은 `project_member` 없이도 모든 프로젝트에 접근 가능
- participant/viewer는 `project_member`에 등록된 프로젝트만 접근 가능
- 서버 최초 실행 시 기본 관리자 자동 생성: `yoonsm@daou.co.kr` / `zaq12wsx` (이름: 윤순무)
- 데코레이터 패턴: `@login_required` (페이지), `@api_login_required` (API), `@project_access_required(min_role)`, `@admin_required`
- 프론트엔드: viewer일 때 편집 버튼 숨김 + contenteditable 비활성화 + 컨텍스트메뉴 차단 + API 403 응답 처리

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
- **레이아웃**: `top-bar → alert-section → toolbar → grid → footer-bar`
- **컬럼**: `# | 구분 | Task | 서브태스크 | 세부항목 | 담당자 | 계획시작 | 계획완료 | 실제시작 | 실제종료 | 공수 | 진행률 | 진행상태`
- **알림 섹션**: 계획완료일 경과 + 진행률 100% 미만인 항목을 칩으로 표시 (지연일수 포함)
- **필터**: 검색(전체 컬럼), 진행률(완료/진행중/미착수), 담당자(동적 드롭다운)
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

## 9. 미구현 / 향후 작업

- [ ] 테스트 코드 작성 (`tests/`)
- [ ] 변경 이력 추적
- [ ] 인쇄/PDF 보고서 출력
- [ ] Chart.js 대시보드 차트 (도넛, 막대 등)
- [ ] Excel Import UI (파일 업로드 폼)
- [ ] 에러 핸들링 고도화 (전역 에러 핸들러)
- [ ] 프로덕션 배포 설정 (waitress/gunicorn)
- [ ] 비밀번호 변경 기능
- [ ] 관리자 사용자 관리 UI (역할 변경, 삭제)

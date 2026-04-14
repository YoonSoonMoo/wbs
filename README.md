# WBS 관리 시스템

> **Work Breakdown Structure** — 프로젝트의 계층적 작업 분해 구조를 웹에서 생성·관리하는 도구

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-black?logo=flask)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-내장-blue?logo=sqlite)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-Private-red)]()

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [주요 기능](#2-주요-기능)
3. [기술 스택](#3-기술-스택)
4. [프로젝트 구조](#4-프로젝트-구조)
5. [데이터베이스 스키마](#5-데이터베이스-스키마)
6. [API 엔드포인트](#6-api-엔드포인트)
7. [권한 체계](#7-권한-체계)
8. [빠른 시작](#8-빠른-시작)
9. [환경 설정](#9-환경-설정)
10. [향후 작업](#10-향후-작업)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | WBS(Work Breakdown Structure) 관리 시스템 |
| 목적 | 프로젝트의 계층적 작업 분해 구조를 웹에서 생성·관리 |
| 저장소 | https://github.com/YoonSoonMoo/wbs |
| 최종 갱신 | 2026-04-10 |

본 시스템은 프로젝트 관리 담당자가 작업(Task)을 계층적으로 정의하고,
일정·담당자·진행률을 한 화면에서 직관적으로 관리할 수 있도록 설계된
**경량 웹 애플리케이션**입니다. 별도의 빌드 도구 없이 Flask 서버만으로
즉시 실행 가능하며, 엑셀·CSV Import/Export와 Gantt 차트 뷰를 함께 제공합니다.

---

## 2. 주요 기능

### 📋 WBS 그리드

- **계층적 트리 구조** — 무제한 depth의 parent-child 관계 지원
- **WBS 코드 자동생성** — 항목 추가·이동·삭제 시 `1.0 / 1.1 / 1.1.1` 형식으로 자동 재계산
- **contenteditable 인라인 편집** — 셀 클릭 즉시 편집, 300 ms debounce 자동 저장
- **컨텍스트 메뉴** — 우클릭으로 행 삽입(위/아래) · 행 복제 · 행 삭제
- **검색 / 필터** — 전체 컬럼 키워드 검색, 진행률 상태別 필터, 담당자 드롭다운
- **컬럼 정렬** — 헤더 클릭으로 오름차순 / 내림차순 토글
- **진행률 색상 바** — 0 % 회색 → 30 % 노랑 → 70 % 파랑 → 100 % 초록
- **지연 업무 알림** — 계획완료일 초과 + 진행률 미만 항목을 칩(Chip)으로 상시 표시

### 📊 대시보드

- 프로젝트 목록 카드 (전체 / 완료 / 진행 / 지연 건수, 평균 진행률)
- 카테고리별·담당자별 통계
- 프로젝트 생성 · 수정 · 삭제 (admin 전용)
- 프로젝트 멤버 할당 UI (참여자 / 뷰어 역할 선택)

### 📅 Gantt 차트

- [Frappe Gantt](https://frappe.io/gantt) 기반 시각화
- 주간 / 월간 / 분기 뷰 전환
- WBS 항목의 계획 일정(plan_start ~ plan_end) 자동 반영

### 📥 Import / Export

| 형식 | Import | Export |
|------|--------|--------|
| CSV | ✅ (파일 업로드 / 붙여넣기) | ✅ (UTF-8 BOM) |
| Excel (.xlsx) | ✅ (탭 구분 붙여넣기) | ✅ (헤더 서식 포함) |

### 🔐 인증 / 권한

- 로그인 · 회원가입 · 로그아웃
- 세션 기반 인증 (Flask session + werkzeug 비밀번호 해싱)
- 역할 기반 접근 제어 (admin / participant / viewer)

---

## 3. 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| Language | Python | 3.x |
| Framework | Flask | 3.1.1 |
| Database | SQLite (내장 `sqlite3`) | — |
| Frontend | Jinja2 + Vanilla JS | — |
| Font | Noto Sans KR + JetBrains Mono | Google Fonts CDN |
| Excel | openpyxl | 3.1.5 |
| Gantt | Frappe Gantt | 0.6.1 (CDN) |
| 환경변수 | python-dotenv | 1.1.0 |
| WSGI | waitress | 3.0.2 (Windows 프로덕션) |
| Test | pytest | 8.3.5 |

> **SPA 프레임워크 미사용** — 빌드 도구 없이 즉시 개발·실행 가능

---

## 4. 프로젝트 구조

```
wbs/
├── app/
│   ├── __init__.py              # Flask 앱 팩토리 (create_app)
│   ├── auth.py                  # 인증 데코레이터
│   ├── config.py                # 환경설정 (Dev / Prod / Test)
│   ├── extensions.py            # DB 헬퍼 (get_db, close_db, init_db)
│   │
│   ├── models/                  # 순수 DB CRUD 쿼리
│   │   ├── project.py           # 프로젝트 CRUD
│   │   └── wbs_item.py          # WBS 항목 CRUD (재귀 CTE 트리 조회)
│   │
│   ├── services/                # 비즈니스 로직
│   │   ├── wbs_service.py       # WBS 핵심 로직 (트리 구축·이동·일괄수정)
│   │   ├── wbs_code_service.py  # WBS 코드 자동생성·재계산
│   │   ├── auth_service.py      # 인증 서비스 (register · login · 역할 조회)
│   │   ├── dashboard_service.py # 대시보드 통계
│   │   └── import_export.py     # CSV / Excel Import · Export
│   │
│   ├── routes/                  # URL 라우팅 (Blueprint)
│   │   ├── __init__.py          # 블루프린트 등록
│   │   ├── auth.py              # /login · /register · /logout
│   │   ├── main.py              # / · /project/<id>/wbs · /gantt
│   │   ├── api_project.py       # /api/projects
│   │   ├── api_wbs.py           # /api/wbs
│   │   └── api_import_export.py # /api/io
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css        # 대시보드 스타일
│   │   │   └── wbs.css          # WBS 그리드 전용 스타일
│   │   ├── js/
│   │   │   ├── app.js           # API 헬퍼·토스트 알림·공통 유틸
│   │   │   ├── grid.js          # WBS 그리드 UI
│   │   │   ├── gantt.js         # Frappe Gantt 래퍼
│   │   │   └── dashboard.js     # 대시보드 UI
│   │   └── lib/                 # 벤더 라이브러리
│   │
│   └── templates/
│       ├── base.html            # 공통 레이아웃
│       ├── login.html           # 로그인
│       ├── register.html        # 회원가입
│       ├── index.html           # 대시보드 (프로젝트 목록)
│       ├── wbs.html             # WBS 그리드 뷰 (독립 페이지)
│       └── gantt.html           # Gantt 차트 뷰
│
├── migrations/
│   ├── 001_initial.sql          # 초기 DB 스키마
│   └── 002_auth.sql             # 인증 스키마
│
├── instance/                    # SQLite DB 파일 (자동 생성, .gitignore)
├── template/
│   └── wbs-manage.html          # UI 레퍼런스 원본 (단독 HTML)
├── tests/                       # 테스트 (미구현)
├── requirements.txt
├── run.py                       # 실행 진입점
└── handoff.md                   # 개발 인수인계 문서
```

### 핵심 설계 원칙

| 결정 | 이유 |
|------|------|
| **Adjacency List** 계층 구조 | 삽입·이동이 잦은 WBS 특성상 Nested Set보다 단순 |
| **재귀 CTE** 트리 조회 | 단일 쿼리로 전체 트리 반환, N+1 쿼리 방지 |
| **ORM 미사용** | sqlite3 내장 모듈로 종속성 최소화, 쿼리 가시성 확보 |
| **WAL 모드** | 동시 읽기 성능 향상 |
| **인라인 편집 + debounce** | 별도 저장 버튼 없이 UX 단순화 |
| **앱 팩토리 패턴** | 환경별 설정·테스트 격리 용이 |

---

## 5. 데이터베이스 스키마

### project

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 프로젝트명 |
| description | TEXT | 설명 |
| start_date | TEXT | 시작일 (YYYY-MM-DD) |
| end_date | TEXT | 종료일 |
| created_at | TEXT | 생성일시 (트리거 자동) |
| updated_at | TEXT | 수정일시 (트리거 자동) |

### wbs_item

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| project_id | INTEGER FK | 소속 프로젝트 |
| parent_id | INTEGER FK | 부모 항목 (`NULL` = 최상위) |
| wbs_code | TEXT | 자동생성 코드 (`1.0`, `1.1`, `1.1.1`) |
| level | INTEGER | 깊이 (0 = 최상위) |
| sort_order | INTEGER | 형제 노드 내 정렬 순서 |
| category | TEXT | 구분 (기획·설계·개발 등) |
| task_name | TEXT | Task 명 |
| subtask | TEXT | 서브태스크 |
| detail | TEXT | 세부항목 |
| description | TEXT | 상세 설명 |
| plan_start | TEXT | 계획 시작일 |
| plan_end | TEXT | 계획 완료일 |
| actual_start | TEXT | 실제 시작일 |
| actual_end | TEXT | 실제 종료일 |
| assignee | TEXT | 담당자 |
| effort | REAL | 공수 (man-day) |
| progress | INTEGER | 진행률 (0 ~ 100) |
| status | TEXT | 진행상태 (`대기` / `진행중` / `완료` / `보류` / `지연`) |
| priority | TEXT | 우선순위 (`low` / `medium` / `high` / `critical`) |
| is_milestone | INTEGER | 마일스톤 여부 (0 / 1) |

### user

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 증가 |
| name | TEXT NOT NULL | 이름 |
| email | TEXT UNIQUE | 이메일 (로그인 ID) |
| password_hash | TEXT NOT NULL | 비밀번호 해시 (werkzeug) |
| role | TEXT | 전역 역할 (`admin` / `participant` / `viewer`) |
| created_at | TEXT | 생성일시 |

### project_member

| 컬럼 | 타입 | 설명 |
|------|------|------|
| project_id | INTEGER FK | 프로젝트 |
| user_id | INTEGER FK | 사용자 |
| role | TEXT | 프로젝트 내 역할 (`participant` / `viewer`) |

> **복합 PK**: `(project_id, user_id)`  
> **admin** 역할 사용자는 `project_member` 미등록 시에도 모든 프로젝트에 접근 가능

#### 인덱스

```sql
idx_wbs_project  -- project_id
idx_wbs_parent   -- parent_id
idx_wbs_code     -- (project_id, wbs_code)
idx_wbs_assignee -- assignee
idx_wbs_sort     -- (parent_id, sort_order)
```

---

## 6. API 엔드포인트

### 인증 (페이지 라우트)

| Method | URL | 설명 |
|--------|-----|------|
| GET/POST | `/login` | 로그인 |
| GET/POST | `/register` | 회원가입 |
| GET | `/logout` | 로그아웃 → `/login` 리다이렉트 |

### 프로젝트 API (`/api/projects`)

| Method | URL | 권한 | 설명 |
|--------|-----|------|------|
| GET | `/api/projects` | 로그인 | 프로젝트 목록 |
| POST | `/api/projects` | admin | 프로젝트 생성 |
| GET | `/api/projects/<id>` | 로그인 | 프로젝트 상세 |
| PUT | `/api/projects/<id>` | admin | 프로젝트 수정 |
| DELETE | `/api/projects/<id>` | admin | 프로젝트 삭제 |
| GET | `/api/projects/<id>/members` | 로그인 | 멤버 목록 |
| GET | `/api/projects/users` | admin | 전체 사용자 목록 |

### WBS API (`/api/wbs`)

| Method | URL | 권한 | 설명 |
|--------|-----|------|------|
| GET | `/api/wbs/<pid>/items` | viewer+ | 항목 목록 (`?mode=flat\|tree`) |
| POST | `/api/wbs/<pid>/items` | participant+ | 항목 추가 |
| GET | `/api/wbs/items/<id>` | viewer+ | 항목 상세 |
| PUT | `/api/wbs/items/<id>` | participant+ | 항목 전체 수정 |
| PATCH | `/api/wbs/items/<id>` | participant+ | 항목 부분 수정 (인라인 편집) |
| DELETE | `/api/wbs/items/<id>` | participant+ | 항목 삭제 (자식 포함 재귀) |
| POST | `/api/wbs/items/<id>/move` | participant+ | 항목 이동 |
| POST | `/api/wbs/<pid>/items/batch` | participant+ | 일괄 수정 |
| GET | `/api/wbs/<pid>/stats` | viewer+ | 진행 통계 |
| GET | `/api/wbs/<pid>/delayed` | viewer+ | 지연 업무 목록 |
| GET | `/api/wbs/<pid>/dashboard` | viewer+ | 대시보드 종합 데이터 |

### Import/Export API (`/api/io`)

| Method | URL | 설명 |
|--------|-----|------|
| GET | `/api/io/<pid>/export/csv` | CSV 다운로드 (UTF-8 BOM) |
| GET | `/api/io/<pid>/export/excel` | Excel 다운로드 (.xlsx) |
| POST | `/api/io/<pid>/import/csv` | CSV 업로드 (multipart/form-data) |
| POST | `/api/io/<pid>/import/paste` | 탭 구분 텍스트 붙여넣기 |

---

## 7. 권한 체계

```
admin
 ├── 모든 프로젝트 생성·수정·삭제
 ├── 사용자 관리 (멤버 할당)
 └── 모든 프로젝트 WBS 읽기·쓰기

participant  (프로젝트별 할당)
 ├── 할당된 프로젝트 WBS 읽기·쓰기
 └── Import / Export

viewer  (프로젝트별 할당)
 └── 할당된 프로젝트 읽기 전용
     (편집 버튼 숨김, contenteditable 비활성화, API 403)
```

### 인증 데코레이터

| 데코레이터 | 용도 |
|-----------|------|
| `@login_required` | 페이지 라우트 인증 |
| `@api_login_required` | API 라우트 인증 (401 JSON 반환) |
| `@project_access_required(min_role)` | 프로젝트별 최소 권한 검사 |
| `@admin_required` | 전역 admin 권한 검사 |

### 기본 관리자 계정

서버 최초 실행 시 자동 생성됩니다.

| 항목 | 값 |
|------|-----|
| 이메일 | `yoonsm@daou.co.kr` |
| 비밀번호 | `zaq12wsx` |
| 이름 | 윤순무 |
| 역할 | admin |

> ⚠️ **운영 환경에서는 반드시 비밀번호를 변경하세요.**

---

## 8. 빠른 시작

### 사전 요구사항

- Python 3.10 이상
- pip

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/YoonSoonMoo/wbs.git
cd wbs

# 2. 가상환경 생성 및 활성화
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행
python run.py

# 5. 브라우저 접속
# http://localhost:5000
```

> 서버 최초 실행 시 `instance/wbs.db` 파일이 자동 생성되고  
> `migrations/` 폴더의 SQL 파일이 순서대로 자동 적용됩니다.

### 프로덕션 실행 (Windows, waitress)

```bash
waitress-serve --host=0.0.0.0 --port=5000 run:app
```

### 테스트 실행

```bash
pytest tests/
```

---

## 9. 환경 설정

`FLASK_ENV` 환경변수로 실행 환경을 선택합니다.

| 값 | 설정 클래스 | DB |
|----|-----------|-----|
| `development` (기본값) | `DevelopmentConfig` | `instance/wbs.db` |
| `production` | `ProductionConfig` | `instance/wbs.db` |
| `testing` | `TestingConfig` | `:memory:` |

### 환경변수

프로젝트 루트에 `.env` 파일을 생성하여 설정합니다.

```dotenv
# Flask 시크릿 키 (운영 시 반드시 변경)
SECRET_KEY=your-secure-secret-key

# 실행 환경 (development / production / testing)
FLASK_ENV=production
```

---

## 10. 향후 작업

| 항목 | 우선순위 |
|------|---------|
| 테스트 코드 작성 (`tests/`) | 높음 |
| 에러 핸들링 고도화 (전역 에러 핸들러) | 높음 |
| 비밀번호 변경 기능 | 중간 |
| 관리자 사용자 관리 UI | 중간 |
| 드래그 앤 드롭 행 이동 | 중간 |
| Chart.js 대시보드 차트 (도넛·막대) | 낮음 |
| Excel Import UI (파일 업로드 폼) | 낮음 |
| 변경 이력 추적 | 낮음 |
| 인쇄 / PDF 보고서 출력 | 낮음 |

---

## 관련 문서

- [handoff.md](./handoff.md) — 개발 인수인계 상세 문서 (설계 결정 배경 포함)
- [migrations/001_initial.sql](./migrations/001_initial.sql) — 초기 DB 스키마
- [migrations/002_auth.sql](./migrations/002_auth.sql) — 인증 스키마
- [template/wbs-manage.html](./template/wbs-manage.html) — UI 레퍼런스 원본

---

*본 문서는 2026-04-13 기준으로 작성되었습니다.*

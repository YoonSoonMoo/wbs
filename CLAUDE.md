# WBS 관리 시스템

상세 핸드오프 문서는 [handoff.md](handoff.md) 참조.

## 빠른 참고

- **기술 스택**: Flask + SQLite (ORM 없음) + Vanilla JS
- **실행**: `python run.py` → http://localhost:5000
- **초기 관리자**: yoonsm@daou.co.kr / zaq12wsx
- **권한**: admin (전체) / participant (WBS 읽기/쓰기) / viewer (읽기 전용)

## grid.js 주요 전역 변수

| 변수 | 용도 |
|------|------|
| `data[]` | WBS 행 배열 (`_id`, `_idx`, `category`, `task_name`, ...) |
| `selectedRows{}` | 선택된 행 인덱스 맵 |
| `DATE_COLS[]` | 날짜 자동변환 대상 컬럼 (`plan_start`, `plan_end`, `actual_start`, `actual_end`) |
| `COLUMNS[]` | 컬럼 정의 순서 |

## 셀 편집 방식

| 컬럼 | 편집 방식 |
|------|-----------|
| 구분, Task, 서브태스크, 담당자, 일자, 공수 | `contenteditable` 인라인 편집 |
| 세부항목, 진행상태 | 더블클릭 팝업 textarea (개행 지원, `expandable` 클래스) |
| 진행률 | 프로그레스 바 표시 (편집 불가) |

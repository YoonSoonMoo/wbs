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
| `selectedRows{}` | 선택된 행 인덱스 맵 (TID 열 클릭) |
| `cellSel` | 셀 선택 범위 `{r1,c1,r2,c2}` — 렌더링된 행 위치 + COLUMNS 인덱스, 앵커=r1/c1 |
| `editingTd` | 현재 인라인 편집 중인 `td` (없으면 null) |
| `DATE_COLS[]` | 날짜 자동변환 대상 컬럼 (`plan_start`, `plan_end`, `actual_start`, `actual_end`) |
| `COLUMNS[]` | 컬럼 정의 순서 |

## 셀 선택·편집 방식 (엑셀 동일)

- **클릭 = 선택**(편집 아님). 드래그 / Shift+클릭 / Shift+방향키로 범위, Ctrl+A 전체
- **편집 진입**: 더블클릭 · F2 · Enter · 문자 입력. 편집 중에만 `contenteditable` 부여
- **Enter** 커밋+아래 이동 / **Tab** 커밋+오른쪽 이동 / **Escape** 취소
- **Delete** 선택 범위 값 삭제 / **Ctrl+C** TSV 복사 / **Ctrl+V** 선택 위치부터 붙여넣기
- 행 선택(TID 열)과 셀 선택은 배타. 행 선택 상태의 Delete는 종전대로 행 삭제

| 컬럼 | 편집기 |
|------|--------|
| 구분, Task, 서브태스크, 담당자, 일자, 공수 | 셀 내 인라인 편집 |
| 세부항목, 진행상태 | 더블클릭 팝업 textarea (개행 지원, `expandable` 클래스) |
| 진행률 | 더블클릭 시 숫자 입력 (평소 프로그레스 바 표시) |

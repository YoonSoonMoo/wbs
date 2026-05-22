-- 011_project_history_flag.sql: 프로젝트별 변경 이력 관리 ON/OFF 플래그
-- 디폴트 0(OFF). 기존 프로젝트는 OFF로 도입된다.

ALTER TABLE project ADD COLUMN history_enabled INTEGER DEFAULT 0;

-- 012_project_notice.sql: 프로젝트 공지사항(그리드 헤더 marquee 표시용)
ALTER TABLE project ADD COLUMN notice TEXT DEFAULT '';

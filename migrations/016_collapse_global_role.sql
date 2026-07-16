-- 016_collapse_global_role.sql: 전역 역할을 관리자/일반(admin/developer) 2단계로 정리
-- 업무 권한(PM/PL/개발자/뷰어)은 프로젝트별(project_member.role)로 일원화되었으므로,
-- 전역 user.role의 'viewer'(기능상 '일반'과 동일)를 'developer'로 통일한다.
-- (project_member.role 은 건드리지 않는다 — 프로젝트별 뷰어 권한은 그대로 유지)

UPDATE user SET role = 'developer' WHERE role = 'viewer';

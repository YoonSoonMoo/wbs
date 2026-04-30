-- 007_remove_admin_members.sql: 전역 admin 유저는 project_member에서 제거
-- (admin은 get_project_role에서 무조건 admin 반환되므로 멤버 등록은 무의미하고
--  멤버 편집 UI에서 후보 dropdown에서 빠지면 row fallback으로 PK 충돌 유발)

DELETE FROM project_member
 WHERE user_id IN (SELECT id FROM user WHERE role = 'admin');

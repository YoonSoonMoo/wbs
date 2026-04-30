-- 008_unify_user_role.sql
-- 권한 관리 정책 변경: 유저 관리(user.role)가 단일 진실 원본.
-- project_member.role은 더 이상 독립적으로 운용되지 않으며 user.role과 동기화되어야 한다.

-- 1) 윤순무(yoonsm@daou.co.kr)를 제외한 모든 유저를 'developer'로 통일.
--    (기존 admin인 다른 계정은 일반 개발자로 강등, viewer였던 인원도 개발자로 승격)
UPDATE user
   SET role = 'developer'
 WHERE email != 'yoonsm@daou.co.kr';

-- 2) project_member.role을 해당 user.role과 일치시킨다.
--    이전에는 project_member.role이 user.role과 무관하게 설정될 수 있어 권한 불일치가 발생했다.
UPDATE project_member
   SET role = (SELECT role FROM user WHERE user.id = project_member.user_id);

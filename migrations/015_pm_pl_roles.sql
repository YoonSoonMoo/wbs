-- 015_pm_pl_roles.sql: project_member.role CHECK 제약을 pm/pl 포함으로 확장
-- 권한 5단계(admin > pm > pl > developer > viewer)로 확장하며,
-- 프로젝트별 역할을 project_member.role 에 저장(권한 판정의 실제 출처로 복귀).
-- 기존 행의 role(developer/viewer)은 그대로 보존되며, admin 이 프로젝트 수정 화면에서
-- 필요한 멤버를 pm/pl 로 재지정하는 흐름으로 운영한다.

PRAGMA foreign_keys = OFF;

CREATE TABLE project_member_new (
    project_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','pm','pl','developer','viewer')),
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES user(id) ON DELETE CASCADE
);
INSERT INTO project_member_new (project_id, user_id, role)
SELECT project_id, user_id, role FROM project_member;
DROP TABLE project_member;
ALTER TABLE project_member_new RENAME TO project_member;

CREATE INDEX IF NOT EXISTS idx_pm_user ON project_member(user_id);
CREATE INDEX IF NOT EXISTS idx_pm_project ON project_member(project_id);

PRAGMA foreign_keys = ON;

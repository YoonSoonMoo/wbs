-- 006_member_admin_role.sql: project_member.role CHECK 제약 확장 (admin 허용)

PRAGMA foreign_keys = OFF;

CREATE TABLE project_member_new (
    project_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','developer','viewer')),
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

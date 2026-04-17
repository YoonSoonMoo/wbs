-- 004_user_mgmt.sql: 유저 비활성 기능 추가 + 역할 이름 변경 (participant -> developer)

PRAGMA foreign_keys = OFF;

-- user 테이블 재생성 (CHECK 갱신 + is_active 추가 + participant → developer 이관)
CREATE TABLE user_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('admin','developer','viewer')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);
INSERT INTO user_new (id, name, email, password_hash, role, is_active, created_at)
SELECT id, name, email, password_hash,
       CASE WHEN role = 'participant' THEN 'developer' ELSE role END,
       1, created_at
FROM user;
DROP TABLE user;
ALTER TABLE user_new RENAME TO user;

-- project_member 재생성 (CHECK 갱신 + participant → developer 이관)
CREATE TABLE project_member_new (
    project_id  INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('developer','viewer')),
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES user(id) ON DELETE CASCADE
);
INSERT INTO project_member_new (project_id, user_id, role)
SELECT project_id, user_id,
       CASE WHEN role = 'participant' THEN 'developer' ELSE role END
FROM project_member;
DROP TABLE project_member;
ALTER TABLE project_member_new RENAME TO project_member;

CREATE INDEX IF NOT EXISTS idx_pm_user ON project_member(user_id);
CREATE INDEX IF NOT EXISTS idx_pm_project ON project_member(project_id);

PRAGMA foreign_keys = ON;

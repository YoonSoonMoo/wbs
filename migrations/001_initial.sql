-- WBS 관리 시스템 초기 스키마

-- 프로젝트 테이블
CREATE TABLE IF NOT EXISTS project (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    start_date  TEXT,
    end_date    TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    updated_at  TEXT DEFAULT (datetime('now','localtime'))
);

-- WBS 항목 테이블
CREATE TABLE IF NOT EXISTS wbs_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL,
    parent_id    INTEGER,
    wbs_code     TEXT NOT NULL DEFAULT '',
    level        INTEGER NOT NULL DEFAULT 0,
    sort_order   INTEGER NOT NULL DEFAULT 0,

    category     TEXT DEFAULT '',
    task_name    TEXT NOT NULL DEFAULT '',
    subtask      TEXT DEFAULT '',
    detail       TEXT DEFAULT '',
    description  TEXT DEFAULT '',

    plan_start   TEXT,
    plan_end     TEXT,
    actual_start TEXT,
    actual_end   TEXT,

    assignee     TEXT DEFAULT '',
    effort       REAL DEFAULT 0,
    progress     INTEGER DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    status       TEXT DEFAULT '대기',

    priority     TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high','critical')),
    is_milestone INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now','localtime')),
    updated_at   TEXT DEFAULT (datetime('now','localtime')),

    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id)  REFERENCES wbs_item(id) ON DELETE SET NULL
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_wbs_project  ON wbs_item(project_id);
CREATE INDEX IF NOT EXISTS idx_wbs_parent   ON wbs_item(parent_id);
CREATE INDEX IF NOT EXISTS idx_wbs_code     ON wbs_item(project_id, wbs_code);
CREATE INDEX IF NOT EXISTS idx_wbs_assignee ON wbs_item(assignee);
CREATE INDEX IF NOT EXISTS idx_wbs_sort     ON wbs_item(parent_id, sort_order);

-- 담당자 마스터
CREATE TABLE IF NOT EXISTS member (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    email      TEXT DEFAULT '',
    role       TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 업데이트 트리거
CREATE TRIGGER IF NOT EXISTS trg_wbs_item_updated
AFTER UPDATE ON wbs_item
FOR EACH ROW
BEGIN
    UPDATE wbs_item SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_project_updated
AFTER UPDATE ON project
FOR EACH ROW
BEGIN
    UPDATE project SET updated_at = datetime('now','localtime') WHERE id = NEW.id;
END;

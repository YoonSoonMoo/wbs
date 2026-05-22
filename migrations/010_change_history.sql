-- 010_change_history.sql: WBS 항목 변경 이력 테이블
-- 추적 필드: detail(세부항목), assignee(담당자), plan_start, plan_end, effort, progress

CREATE TABLE IF NOT EXISTS wbs_change_history (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id         INTEGER NOT NULL,
    item_id            INTEGER,
    changed_at         TEXT DEFAULT (datetime('now','localtime')),
    changed_by         TEXT DEFAULT '',
    field              TEXT NOT NULL,
    old_value          TEXT DEFAULT '',
    new_value          TEXT DEFAULT '',
    snapshot_detail    TEXT DEFAULT '',
    snapshot_assignee  TEXT DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)    REFERENCES wbs_item(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_hist_project ON wbs_change_history(project_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_hist_item    ON wbs_change_history(item_id);

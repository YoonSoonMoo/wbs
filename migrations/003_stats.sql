-- 003_stats.sql: 수정자 및 완료일시 컬럼 추가

ALTER TABLE wbs_item ADD COLUMN updated_by TEXT DEFAULT '';
ALTER TABLE wbs_item ADD COLUMN completed_at TEXT;

-- 진행률이 100이 될 때 completed_at 자동 기록
CREATE TRIGGER IF NOT EXISTS trg_wbs_completed
AFTER UPDATE OF progress ON wbs_item
FOR EACH ROW
WHEN NEW.progress = 100 AND (OLD.progress IS NULL OR OLD.progress < 100)
BEGIN
    UPDATE wbs_item SET completed_at = datetime('now','localtime') WHERE id = NEW.id;
END;

-- 진행률이 100 미만으로 되돌아가면 completed_at 초기화
CREATE TRIGGER IF NOT EXISTS trg_wbs_uncompleted
AFTER UPDATE OF progress ON wbs_item
FOR EACH ROW
WHEN NEW.progress < 100 AND OLD.progress = 100
BEGIN
    UPDATE wbs_item SET completed_at = NULL WHERE id = NEW.id;
END;

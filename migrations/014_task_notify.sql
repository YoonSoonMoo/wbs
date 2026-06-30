-- 014_task_notify.sql: 프로젝트별 태스크 갱신 알림 자동 메일 설정
-- task_notify_enabled: 자동 발송 ON/OFF (0=OFF, 1=ON, 기본 0)
-- task_notify_time: 발송 시각 'HH:MM' (24h, 기본 09:00). 평일에만 발송
ALTER TABLE project ADD COLUMN task_notify_enabled INTEGER DEFAULT 0;
ALTER TABLE project ADD COLUMN task_notify_time TEXT DEFAULT '09:00';

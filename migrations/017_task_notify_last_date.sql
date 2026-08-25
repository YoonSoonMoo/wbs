-- 017_task_notify_last_date.sql: 태스크 알림 일일 처리 이력 (재기동 시 중복 발송 방지)
-- task_notify_last_date: 그날의 알림이 마지막으로 처리된 날짜 'YYYY-MM-DD'.
--   발송 완료뿐 아니라 '발송시각을 크게 지나 건너뜀'도 기록해 하루 1회를 보장한다.
--   메모리에만 기록하던 이전 방식은 프로세스가 재기동되면 초기화되어,
--   기동 시각이 발송시각을 지났으면 그날 이미 보낸 메일을 다시 보냈다.
ALTER TABLE project ADD COLUMN task_notify_last_date TEXT;

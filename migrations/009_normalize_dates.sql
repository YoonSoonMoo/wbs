-- 2자리 연도(YY-MM-DD)로 저장된 일자 컬럼을 4자리(20YY-MM-DD)로 정규화.
-- Frappe Gantt가 'YY'를 1900년대로 해석해 차트 가로 폭이 100년에 걸쳐지는 버그 차단.
UPDATE wbs_item SET plan_start   = '20' || plan_start
 WHERE plan_start   GLOB '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]';
UPDATE wbs_item SET plan_end     = '20' || plan_end
 WHERE plan_end     GLOB '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]';
UPDATE wbs_item SET actual_start = '20' || actual_start
 WHERE actual_start GLOB '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]';
UPDATE wbs_item SET actual_end   = '20' || actual_end
 WHERE actual_end   GLOB '[0-9][0-9]-[0-9][0-9]-[0-9][0-9]';

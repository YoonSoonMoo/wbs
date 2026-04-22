-- 005_password_reset.sql: 임시 비밀번호 로그인 후 변경을 위한 컬럼 추가

ALTER TABLE user ADD COLUMN requires_password_change INTEGER DEFAULT 0;

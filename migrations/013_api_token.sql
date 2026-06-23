-- 013_api_token.sql: Claude CLI 등 외부 클라이언트용 API 토큰
-- 고엔트로피 랜덤 토큰을 SHA-256 해시로 저장한다 (평문 미저장, 직접 인덱스 조회).

ALTER TABLE user ADD COLUMN api_token_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_user_api_token ON user (api_token_hash);

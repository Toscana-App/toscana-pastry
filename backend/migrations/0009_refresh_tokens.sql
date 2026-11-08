-- 0009_refresh_tokens
-- Refresh token rotation + revocation (docs/specs/security.md item 9).
-- One row per issued refresh token, keyed by jti (the token is never stored).
-- revoked_at set = consumed by a rotation, or revoked by logout / replay.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE TABLE IF NOT EXISTS refresh_tokens (
  jti VARCHAR PRIMARY KEY,
  user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id VARCHAR NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id ON refresh_tokens (family_id);

-- Downgrade
-- DROP TABLE IF EXISTS refresh_tokens;

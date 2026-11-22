-- 0014_google_nonces
-- Server-issued Google Sign-In nonces (docs/specs/p01_auth.md RF-P1-09).
-- One row per pre-auth cookie (google_preauth carries the row id); the nonce
-- itself is embedded by Google into the ID token it returns.
-- consumed_at set = consumed by a sign-in; a replayed token then fails.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE TABLE IF NOT EXISTS google_nonces (
  id UUID PRIMARY KEY,
  nonce TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_google_nonces_expires_at ON google_nonces (expires_at);

-- Downgrade
-- DROP TABLE IF EXISTS google_nonces;

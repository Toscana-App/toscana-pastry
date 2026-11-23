-- 0015_order_idempotency_keys
-- Idempotency keys for portal order creation (docs/specs/p11_portal_checkout.md RF-P11-02).
-- One row per (user, key): the key scopes to the user that created the order
-- and expires 24 h after creation (TTL). Same key + same body replays the
-- original order (no duplicate coupon consumption); same key + different
-- body is rejected with 422 idempotency_key_mismatch.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE TABLE IF NOT EXISTS order_idempotency_keys (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  order_id TEXT NOT NULL REFERENCES orders(id),
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_order_idempotency_keys_user_id ON order_idempotency_keys (user_id);
CREATE INDEX IF NOT EXISTS ix_order_idempotency_keys_order_id ON order_idempotency_keys (order_id);
CREATE INDEX IF NOT EXISTS ix_order_idempotency_keys_expires_at ON order_idempotency_keys (expires_at);

-- Downgrade
-- DROP TABLE IF EXISTS order_idempotency_keys;

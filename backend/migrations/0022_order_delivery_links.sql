-- 0022_order_delivery_links.sql
-- S1/S5 — link publico de entrega por pedido: token uuid4 activo hasta la
-- entrega. Indice unico parcial: un solo link activo por pedido.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE TABLE IF NOT EXISTS order_delivery_links (
  token VARCHAR(36) PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  revoked_reason VARCHAR(20)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_order_delivery_links_active
  ON order_delivery_links (order_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_order_delivery_links_order_id
  ON order_delivery_links (order_id);

-- Downgrade
-- DROP TABLE IF EXISTS order_delivery_links;

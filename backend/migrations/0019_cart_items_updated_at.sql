-- 0019: cart_items.updated_at para el TTL del carrito.
ALTER TABLE cart_items ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

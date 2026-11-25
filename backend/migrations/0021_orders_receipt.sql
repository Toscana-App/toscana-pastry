-- 0021_orders_receipt.sql
-- S2 — Campos de comprobante de transferencia sobre orders.
-- Idempotente: ADD COLUMN IF NOT EXISTS (patron 0013/0015).

-- Upgrade

ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_file TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_content_type TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_size_bytes INTEGER;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_uploaded_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_viewed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS receipt_deleted_at TIMESTAMP WITH TIME ZONE;

-- Downgrade

-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_file;
-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_content_type;
-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_size_bytes;
-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_uploaded_at;
-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_viewed_at;
-- ALTER TABLE orders DROP COLUMN IF EXISTS receipt_deleted_at;

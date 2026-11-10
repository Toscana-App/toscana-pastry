-- 0011_orders_date_status_index
-- Composite index for the admin dashboard aggregates: every query filters
-- orders by a date range and then by status != 'cancelado'.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE INDEX IF NOT EXISTS ix_orders_date_status ON orders (date, status);

-- Downgrade
-- DROP INDEX IF EXISTS ix_orders_date_status;

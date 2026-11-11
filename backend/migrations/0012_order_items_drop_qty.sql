-- 0012_order_items_drop_qty
-- Target: PostgreSQL. Run once per database (not idempotent: drops a column).
-- (Tests run the portable section below against SQLite; see
--  tests/integration/data/test_migration_0012.py.)
-- order_items carried a redundant qty column dual-written in parallel with
-- the canonical quantity (see data/repositories/sql_order_repository.py).
-- quantity is kept; qty is dropped. Fresh databases get the slim schema
-- from Base.metadata.create_all; this script is for existing databases.

-- === upgrade (portable) ===
-- Defensive: reconcile the redundant copy with the canonical one before
-- dropping it (they are dual-written, so in practice they already agree).
UPDATE order_items SET qty = quantity WHERE qty IS DISTINCT FROM quantity;
ALTER TABLE order_items DROP COLUMN qty;

-- === upgrade (postgres only) ===
-- nothing

-- === downgrade (commented; the redundant column comes back, backfilled) ===
-- ALTER TABLE order_items ADD COLUMN qty INTEGER;
-- UPDATE order_items SET qty = quantity;

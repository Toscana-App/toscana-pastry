-- 0011_orders_customer_fk
-- Enforce orders.customer_id -> customers.id at the DB level. There is no
-- customer delete path, so the implicit RESTRICT is the intended behavior.
-- If orphan rows exist the migration fails on purpose: it exposes a data
-- bug, and no known seed data is orphaned.
-- Fresh databases get it from Base.metadata.create_all; this script is for
-- existing databases (apply in order 0001..0011).

-- Upgrade
ALTER TABLE orders
    ADD CONSTRAINT fk_orders_customer_id
    FOREIGN KEY (customer_id) REFERENCES customers (id);

-- Downgrade
-- ALTER TABLE orders DROP CONSTRAINT fk_orders_customer_id;

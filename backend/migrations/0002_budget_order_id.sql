-- 0002_budget_order_id: link a budget to the order created from it (RF-P8-08).
-- Fresh databases get this from Base.metadata.create_all (BudgetORM.order_id);
-- apply this script to databases created before it.

-- upgrade
ALTER TABLE budgets ADD COLUMN order_id VARCHAR REFERENCES orders (id) ON DELETE SET NULL;
CREATE INDEX ix_budgets_order_id ON budgets (order_id);

-- downgrade
-- DROP INDEX IF EXISTS ix_budgets_order_id;
-- ALTER TABLE budgets DROP COLUMN order_id;

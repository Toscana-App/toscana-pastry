ALTER TABLE budgets ADD COLUMN order_id VARCHAR REFERENCES orders (id) ON DELETE SET NULL;
CREATE INDEX ix_budgets_order_id ON budgets (order_id);

DROP INDEX IF EXISTS ix_budgets_seq;
CREATE UNIQUE INDEX ix_budgets_seq ON budgets (seq);

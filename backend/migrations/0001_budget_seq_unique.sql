-- 0001_budget_seq_unique: unique budget sequence (#000NN) per tenant (RNF-P8-04).
-- Last line of defense against duplicate sequences under concurrency.
-- Fresh databases get this from Base.metadata.create_all (unique=True on
-- BudgetORM.seq, index ix_budgets_seq); apply this script to databases
-- created before it. Fails if duplicate seq values already exist: resolve
-- them first.

-- upgrade
DROP INDEX IF EXISTS ix_budgets_seq;
CREATE UNIQUE INDEX ix_budgets_seq ON budgets (seq);

-- downgrade
-- DROP INDEX IF EXISTS ix_budgets_seq;
-- CREATE INDEX ix_budgets_seq ON budgets (seq);

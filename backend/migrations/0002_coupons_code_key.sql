-- 0002_coupons_code_key: persisted normalized code with a UNIQUE constraint.
-- Stacked on 0001_customer_addresses_one_default.sql (PR #25).

-- ===== upgrade =====
ALTER TABLE coupons ADD COLUMN code_key VARCHAR;

-- Backfill BEFORE the unique constraint. lower() only: the app computes
-- code_key with accent_fold (NFD, strip combining marks, lower). Legacy rows
-- with accented codes therefore get an unfolded key here; re-run the app-side
-- fold for them (UPDATE coupons SET code_key = accent_fold(code)) if needed.
-- If two legacy codes collide after lower(), the index below fails: resolve
-- the duplicates manually first.
UPDATE coupons SET code_key = lower(code) WHERE code_key IS NULL;

CREATE UNIQUE INDEX uq_coupons_code_key ON coupons (code_key);
-- PostgreSQL: also run ALTER TABLE coupons ALTER COLUMN code_key SET NOT NULL;
-- (SQLite cannot alter nullability without a table rebuild.)

-- ===== downgrade (commented) =====
-- DROP INDEX uq_coupons_code_key;
-- ALTER TABLE coupons DROP COLUMN code_key;

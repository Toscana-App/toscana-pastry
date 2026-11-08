ALTER TABLE coupons ADD COLUMN code_key VARCHAR;

UPDATE coupons SET code_key = lower(code) WHERE code_key IS NULL;

CREATE UNIQUE INDEX uq_coupons_code_key ON coupons (code_key);

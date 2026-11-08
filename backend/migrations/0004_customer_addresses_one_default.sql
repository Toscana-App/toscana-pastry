UPDATE customer_addresses
SET is_default = FALSE
WHERE is_default
  AND id NOT IN (
    SELECT DISTINCT ON (user_id) id
    FROM customer_addresses
    WHERE is_default
    ORDER BY user_id, created_at, id
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_addresses_one_default_per_user
    ON customer_addresses (user_id)
    WHERE is_default;

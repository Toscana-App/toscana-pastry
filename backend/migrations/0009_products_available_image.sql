ALTER TABLE products ADD COLUMN available BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE products ADD COLUMN image_url VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_products_available ON products (available);

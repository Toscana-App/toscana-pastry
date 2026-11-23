-- 0016: tags de restricción en productos (P3/P4, RF-P4-01 / RF-P3-07)
ALTER TABLE products
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]';

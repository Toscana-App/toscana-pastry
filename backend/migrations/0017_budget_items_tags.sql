-- 0017: snapshot de tags de producto por item de presupuesto
ALTER TABLE budget_items
    ADD COLUMN tags JSONB NOT NULL DEFAULT '[]';

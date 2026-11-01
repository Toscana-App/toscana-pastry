-- 0001_calc_product_version_unique
-- Un producto no puede tener dos versiones con el mismo version_number
-- (RF-P4CC-07, append-only). Protege contra recalculos concurrentes.

-- Upgrade
ALTER TABLE calc_product_versions
    ADD CONSTRAINT uq_calc_product_versions_product_version
    UNIQUE (product_id, version_number);

-- Downgrade
-- ALTER TABLE calc_product_versions
--     DROP CONSTRAINT uq_calc_product_versions_product_version;

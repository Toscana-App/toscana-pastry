ALTER TABLE calc_product_versions
    ADD CONSTRAINT uq_calc_product_versions_product_version
    UNIQUE (product_id, version_number);

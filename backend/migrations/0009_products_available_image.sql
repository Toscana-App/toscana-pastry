-- 0009_products_available_image
-- Switch de publicacion (P12 S2) + ruta de imagen (P12 S3). available=false:
-- solo vitrina admin; true: catalogo del portal. image_url lo gestionan los
-- endpoints de imagen (upload/delete), nunca el cliente.
-- Fresh databases lo obtienen de Base.metadata.create_all; este script es
-- para bases ya creadas (aplicar en orden 0001..0009).

-- Upgrade
ALTER TABLE products ADD COLUMN available BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE products ADD COLUMN image_url VARCHAR(255);
CREATE INDEX IF NOT EXISTS ix_products_available ON products (available);

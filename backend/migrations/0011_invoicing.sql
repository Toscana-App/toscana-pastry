-- 0011_invoicing
-- P13 — Facturación electrónica ARCA (docs/specs/p13_invoicing.md).
-- Comprobantes (Factura C + CAE) emitidos por pedido, ítems del comprobante
-- (detalle para el PDF) y settings singleton de facturación.
-- Fresh databases get them from Base.metadata.create_all; this script is for
-- existing databases.

-- Upgrade
CREATE TABLE IF NOT EXISTS invoicing_settings (
  id VARCHAR PRIMARY KEY DEFAULT 'singleton',
  cuit VARCHAR(11) NOT NULL,
  punto_venta INTEGER NOT NULL,
  razon_social VARCHAR NOT NULL DEFAULT '',
  domicilio VARCHAR NOT NULL DEFAULT '',
  condicion_iva VARCHAR NOT NULL DEFAULT 'Responsable Monotributo',
  categoria_monotributo VARCHAR(1) NOT NULL DEFAULT '',
  ingresos_brutos VARCHAR NOT NULL DEFAULT '',
  inicio_actividades VARCHAR NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS invoices (
  id VARCHAR PRIMARY KEY,
  order_id VARCHAR NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
  punto_venta INTEGER NOT NULL,
  tipo_cbte INTEGER NOT NULL,
  numero INTEGER NOT NULL,
  cae VARCHAR(14) NOT NULL,
  cae_vto DATE NOT NULL,
  fecha DATE NOT NULL,
  imp_total VARCHAR NOT NULL,
  condicion_iva VARCHAR NOT NULL DEFAULT 'Responsable Monotributo',
  estado VARCHAR(1) NOT NULL DEFAULT 'A',
  obs TEXT NOT NULL DEFAULT '',
  receptor_doc_tipo INTEGER NOT NULL,
  receptor_doc_nro INTEGER NOT NULL,
  receptor_nombre VARCHAR NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  CONSTRAINT uq_invoices_pvt_tipo_numero UNIQUE (punto_venta, tipo_cbte, numero)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoices_order_id ON invoices (order_id);
CREATE INDEX IF NOT EXISTS ix_invoices_fecha ON invoices (fecha);

CREATE TABLE IF NOT EXISTS invoice_items (
  id VARCHAR PRIMARY KEY,
  invoice_id VARCHAR NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  descripcion VARCHAR NOT NULL,
  cantidad NUMERIC NOT NULL,
  precio_unit VARCHAR NOT NULL,
  position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_invoice_items_invoice_id ON invoice_items (invoice_id);

-- Downgrade
-- DROP TABLE IF EXISTS invoice_items;
-- DROP TABLE IF EXISTS invoices;
-- DROP TABLE IF EXISTS invoicing_settings;

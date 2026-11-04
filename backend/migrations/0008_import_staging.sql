-- 0008_import_staging
-- Staging de importacion CSV (RF-CSV-01/03/07/11). Sesion + filas estadiadas;
-- las filas se validan contra la plantilla antes de confirmar. La tabla se
-- limpia al confirmar (RF-CSV-05) y expira a los 7 dias (RF-CSV-07).
-- Fresh databases lo obtienen de Base.metadata.create_all; este script es para
-- bases ya creadas. `template_columns`, `data` y `errors` son JSON serializado
-- (mismo patron que los snapshots de presupuesto).

-- Upgrade
CREATE TABLE IF NOT EXISTS import_sessions (
  id VARCHAR PRIMARY KEY,
  tenant_id VARCHAR NOT NULL,
  user_id VARCHAR NOT NULL,
  entity VARCHAR NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'received',
  filename VARCHAR NOT NULL,
  delimiter VARCHAR NOT NULL,
  encoding VARCHAR NOT NULL,
  template_columns TEXT NOT NULL,
  total_rows INTEGER NOT NULL DEFAULT 0,
  valid_rows INTEGER NOT NULL DEFAULT 0,
  invalid_rows INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL,
  confirmed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS import_rows (
  id VARCHAR PRIMARY KEY,
  import_id VARCHAR NOT NULL REFERENCES import_sessions(id) ON DELETE CASCADE,
  tenant_id VARCHAR NOT NULL,
  row_number INTEGER NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'valid',
  data TEXT NOT NULL,
  errors TEXT NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_import_sessions_tenant ON import_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS ix_import_sessions_status ON import_sessions (status);
CREATE INDEX IF NOT EXISTS ix_import_sessions_created ON import_sessions (created_at);
CREATE INDEX IF NOT EXISTS ix_import_rows_import ON import_rows (import_id);
CREATE INDEX IF NOT EXISTS ix_import_rows_tenant ON import_rows (tenant_id);

-- Downgrade
-- DROP TABLE IF EXISTS import_rows;
-- DROP TABLE IF EXISTS import_sessions;

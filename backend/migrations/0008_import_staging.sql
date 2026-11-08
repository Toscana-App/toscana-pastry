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

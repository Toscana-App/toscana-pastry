/**
 * Tipos del módulo de importación CSV (T-CSV-8).
 *
 * Espejo 1:1 del contrato `backend/src/api/v1/imports/`:
 * - `entity`: ingredients | products | customers.
 * - Money (`precio_*`) viaja como long de centavos (int) en el dominio, pero
 *   en el CSV y en `values` es string decimal (convención argentina).
 * - `values` de cada fila: dict columna→valor tal como viene del CSV.
 */

export const IMPORT_ENTITIES = ["ingredients", "products", "customers"] as const;
export type ImportEntity = (typeof IMPORT_ENTITIES)[number];

/** Etiquetas humanas por entidad (para títulos/descripciones del dialog). */
export const ENTITY_LABELS: Record<ImportEntity, string> = {
  ingredients: "insumos",
  products: "productos",
  customers: "clientes",
};

export type ImportRowStatus = "valid" | "invalid";
export type ImportStatus = "staged" | "confirmed" | "discarded";

/** POST /imports (upload). */
export interface ImportUploadResponse {
  import_id: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
}

/** GET /imports/{id}/rows — una fila staged. */
export interface ImportRowOut {
  row_number: number;
  values: Record<string, string>;
  status: ImportRowStatus;
  errors: string[];
}

/** GET /imports/{id}/rows — paginado. */
export interface ImportRowsResponse {
  import_id: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  rows: ImportRowOut[];
  page: number;
  page_size: number;
}

/** POST /imports/{id}/confirm. `message` solo cuando la entidad no inserta. */
export interface ConfirmResponse {
  created: number;
  skipped: number;
  errors: string[];
  message?: string;
}

/** DELETE /imports/{id}. */
export interface DiscardResponse {
  discarded: boolean;
}

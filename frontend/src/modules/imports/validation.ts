import type { ImportEntity } from "./types";

/**
 * Validación client-side de la importación CSV (RF-CSV-02/13, primera línea).
 *
 * Funciones puras, sin I/O ni red: el dialog las usa para rechazar el archivo
 * ANTES de subirlo. El backend sigue siendo la validación autoritativa.
 */

export interface ColumnDiff {
  ok: boolean;
  /** Columnas de la plantilla que faltan en el archivo. */
  missing: string[];
  /** Columnas del archivo ajenas a la plantilla. */
  extra: string[];
}

/**
 * Compara el set de encabezados contra la plantilla. El set debe coincidir
 * EXACTAMENTE (orden irrelevante). Cualquier columna faltante o extra → no ok.
 */
export function compareColumns(
  expected: string[],
  actual: string[],
): ColumnDiff {
  const exp = new Set(expected);
  const act = new Set(actual);
  const missing = expected.filter((c) => !act.has(c));
  const extra = actual.filter((c) => !exp.has(c));
  return { ok: missing.length === 0 && extra.length === 0, missing, extra };
}

/**
 * Número con convención argentina: coma decimal, punto como separador de miles
 * (p. ej. `1.234,56`). Tolerante: también acepta `1234.56` y enteros.
 */
export function isDecimal(raw: string): boolean {
  const s = raw.replace(/\s/g, "");
  if (s === "") return false;
  const cleaned = s.replace(/\./g, "").replace(",", ".");
  if (cleaned === "" || cleaned === ".") return false;
  return !Number.isNaN(Number(cleaned));
}

export interface ColumnSpec {
  /** Clave de columna (idéntica al encabezado de la plantilla). */
  key: string;
  kind: "text" | "number" | "money";
  required: boolean;
}

/**
 * Espejo de las columnas de los adapters del backend. Sirve para el chequeo
 * básico por fila (requeridos + numéricos) y como fallback de las columnas
 * esperadas si no se pudo descargar la plantilla.
 */
export const ENTITY_COLUMNS: Record<ImportEntity, ColumnSpec[]> = {
  ingredients: [
    { key: "nombre", kind: "text", required: true },
    { key: "unidad", kind: "text", required: true },
    { key: "precio_por_unidad", kind: "money", required: true },
    { key: "cantidad_inicial", kind: "number", required: false },
    { key: "stock_minimo", kind: "number", required: false },
  ],
  products: [
    { key: "nombre", kind: "text", required: true },
    { key: "nombre_corto", kind: "text", required: false },
    { key: "descripcion", kind: "text", required: false },
    { key: "categoria", kind: "text", required: true },
    { key: "precio_venta", kind: "money", required: true },
    { key: "precio_sugerido", kind: "money", required: false },
  ],
  customers: [
    { key: "nombre", kind: "text", required: true },
    { key: "telefono", kind: "text", required: true },
  ],
};

/**
 * Chequeos básicos por fila: campos requeridos no vacíos y numéricos parseables
 * como decimal. Devuelve los errores en español (vacio si la fila está OK).
 */
export function validateRowBasic(
  spec: ColumnSpec[],
  row: Record<string, string>,
): string[] {
  const errors: string[] = [];
  for (const col of spec) {
    const raw = (row[col.key] ?? "").trim();
    if (col.required && raw === "") {
      errors.push(`Faltan datos obligatorios en "${col.key}".`);
      continue;
    }
    if (
      (col.kind === "number" || col.kind === "money") &&
      raw !== "" &&
      !isDecimal(raw)
    ) {
      errors.push(`"${col.key}" debe ser un número (usá coma para los decimales).`);
    }
  }
  return errors;
}

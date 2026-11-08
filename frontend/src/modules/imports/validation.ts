import type { ImportEntity } from "./types";


export interface ColumnDiff {
  ok: boolean;
  missing: string[];
  extra: string[];
}

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

export function isDecimal(raw: string): boolean {
  const s = raw.replace(/\s/g, "");
  if (s === "") return false;
  const cleaned = s.replace(/\./g, "").replace(",", ".");
  if (cleaned === "" || cleaned === ".") return false;
  return !Number.isNaN(Number(cleaned));
}

export interface ColumnSpec {
  key: string;
  kind: "text" | "number" | "money";
  required: boolean;
}

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

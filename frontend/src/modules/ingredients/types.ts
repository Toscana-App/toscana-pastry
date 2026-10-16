/**
 * Tipos del módulo de ingredientes (Fase 4, WU4).
 *
 * Espejo 1:1 de `backend/src/api/v1/ingredients/schemas.py`. Reglas del
 * contrato (RF-04/RF-05):
 * - Money y Qty viajan SIEMPRE como string (Money/Qty serializan como str).
 * - `status` es computado por el servidor: el frontend NUNCA lo calcula ni lo
 *   manda en payloads (solo se re-computa localmente para optimistic UI).
 * - Sin `created_at` en la response de ingrediente.
 * - Unidades fijas: kg | g | L | ml | unidad.
 */

export const INGREDIENT_UNITS = ["kg", "g", "L", "ml", "unidad"] as const;
export type IngredientUnit = (typeof INGREDIENT_UNITS)[number];

/** Motivos aceptados por POST /ingredients/{id}/stock (Literal del backend). */
export const STOCK_REASONS = ["compra", "merma", "ajuste"] as const;
export type StockReason = (typeof STOCK_REASONS)[number];

export type IngredientStatus = "OK" | "LOW" | "EMPTY";

/** GET /ingredients — ítem del listado (RF-P2-01). */
export interface Ingredient {
  id: string;
  name: string;
  unit: IngredientUnit;
  price_per_unit: string;
  stock_qty: string;
  low_stock_threshold: string;
  status: IngredientStatus;
}

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

/** Parámetros de GET /ingredients (todos opcionales; backend valida). */
export interface IngredientListParams {
  q?: string;
  status?: IngredientStatus;
  page?: number;
  page_size?: number;
}

/**
 * Movimiento de stock.
 * El backend registra el stock inicial como `compra` con ref="inicial"
 * (tanto en el alta como en la importación).
 */
export interface StockMovement {
  id: string;
  qty_delta: string;
  reason: string;
  ref: string | null;
  created_at: string; // ISO 8601
}

/**
 * GET /ingredients/{id}?include_movements=true.
 * `movements` es null cuando no se pidieron; el detalle trae los últimos 50.
 */
export interface IngredientDetailResponse {
  ingredient: Ingredient;
  movements: StockMovement[] | null;
}

/** POST /ingredients (RF-P2-02). */
export interface IngredientCreateInput {
  name: string;
  unit: IngredientUnit;
  price_per_unit: number;
  stock_qty: number;
  low_stock_threshold: number;
}

/** PATCH /ingredients/{id} — al menos un campo (extra=forbid en el backend). */
export type IngredientUpdateInput = Partial<
  Pick<
    IngredientCreateInput,
    "name" | "unit" | "price_per_unit" | "low_stock_threshold"
  >
>;

/** POST /ingredients/{id}/stock (RF-P2-03). */
export interface StockAdjustInput {
  delta: number;
  reason: StockReason;
  ref?: string;
}

/** Response del ajuste: stock resultante + movimiento creado. */
export interface StockAdjustmentResponse {
  stock_qty: string;
  movement: StockMovement;
}

/** POST /ingredients/import (RF-P2-06). */
export interface ImportErrorItem {
  line: number;
  message: string;
}

export interface ImportResponse {
  created: number;
  errors: ImportErrorItem[];
}

/** 409 de DELETE /ingredients/{id} (UC-05): el ingrediente está en recetas. */
export interface DeleteImpact {
  impacted_recipes: number;
}

/**
 * Espejo del cálculo de status del backend (`domain/stock.py`):
 * EMPTY si 0, LOW si <= umbral, OK si > umbral.
 * Solo para optimistic UI; el valor autoritativo viene del servidor.
 */
export function statusOf(
  qty: string | number,
  threshold: string | number,
): IngredientStatus {
  const q = Number(qty);
  const t = Number(threshold);
  if (q === 0) return "EMPTY";
  if (q <= t) return "LOW";
  return "OK";
}

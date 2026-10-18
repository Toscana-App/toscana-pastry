/**
 * Tipos del módulo de productos (Fase 5, P3/P4).
 *
 * Espejo 1:1 de `backend/src/api/v1/products/schemas.py`. Reglas del contrato:
 * - Money viaja como long de centavos (int); Qty como string decimal.
 * - `margin_pct` es Pct: string decimal (porcentaje, sin centavos).
 * - El precio NUNCA se persiste: el backend lo deriva en cada lectura con los
 *   insumos y settings actuales (RF-P3-04).
 * - `complete=false` → `price` null + `missing_ingredients` poblado: el
 *   producto existe pero tiene insumos sin precio (0, borrados o inexistentes).
 * - RBAC (como ingredientes): lectura para cualquier usuario autenticado,
 *   mutaciones solo admin.
 */

export const PRODUCT_DIFFICULTIES = ["simple", "intermedio", "complejo"] as const;
export type ProductDifficulty = (typeof PRODUCT_DIFFICULTIES)[number];

/** Unidades de las líneas de receta: el mismo conjunto fijo de insumos. */
export const RECIPE_UNITS = ["kg", "g", "L", "ml", "unidad"] as const;
export type RecipeUnit = (typeof RECIPE_UNITS)[number];

/** GET /products — ítem del listado P3. */
export interface ProductListItem {
  id: string;
  name: string;
  category: string;
  /** Precio comercial redondeado por el motor, en centavos; null si es incompleto. */
  price_final: number | null;
  /** Precio por porción, en centavos. */
  price_per_serving: number | null;
  /** false → la receta tiene insumos sin precio (badge "sin precio", RF-P3-05). */
  complete: boolean;
}

/** GET /products — respuesta con categorías derivadas de los productos activos. */
export interface ProductListResponse {
  items: ProductListItem[];
  total: number;
  page: number;
  page_size: number;
  categories: string[];
}

/** Parámetros de GET /products (todos opcionales; backend valida). */
export interface ProductListParams {
  q?: string;
  category?: string;
  page?: number;
  page_size?: number;
}

/** Desglose completo del motor de precios (tab Costos del P4). Money en centavos. */
export interface PriceBreakdown {
  materials: number;
  waste: number;
  materials_con_merma: number;
  labor: number;
  gas: number;
  base: number;
  /** Porcentaje aplicado (Pct): string decimal, sin centavos. */
  margin_pct: string;
  final: number;
  rounded: number;
}

/** Línea de receta en el detalle, con los datos del insumo corrientes. */
export interface RecipeItemDetail {
  ingredient_id: string;
  ingredient_name: string;
  qty: string;
  unit: string;
  /** Unidad de compra del insumo (kg, L, …); null si el insumo ya no existe. */
  purchase_unit: string | null;
  /** Precio por unidad de compra del insumo, en centavos. */
  price_per_unit: number | null;
  /** Costo de la línea, en centavos; null cuando missing=true. */
  line_cost: number | null;
  missing: boolean;
}

/** GET /products/{id} — detalle P4. */
export interface ProductDetail {
  id: string;
  name: string;
  category: string;
  description: string;
  prep_time_min: number;
  servings: number;
  difficulty: string;
  complete: boolean;
  missing_ingredients: string[];
  price: PriceBreakdown | null;
  /** Precio por porción, en centavos. */
  price_per_serving: number | null;
  recipe: RecipeItemDetail[];
}

/** Línea de receta en requests (Qty/price como number; Pydantic → Decimal). */
export interface RecipeItemInput {
  ingredient_id: string;
  qty: number;
  unit: RecipeUnit;
}

/** POST /products (RF-P4-01). */
export interface ProductCreateInput {
  name: string;
  category: string;
  description?: string;
  prep_time_min?: number;
  servings?: number;
  difficulty?: ProductDifficulty;
  /** Mínimo 1 línea (backend valida). */
  recipe: RecipeItemInput[];
}

/** PATCH /products/{id} — parcial, al menos un campo (extra=forbid en backend). */
export interface ProductUpdateInput
  extends Partial<Omit<ProductCreateInput, "recipe">> {
  /** Cuando se envía, reemplaza la receta completa. */
  recipe?: RecipeItemInput[];
}

/** 409 de DELETE /products/{id} (UC-07): el producto tiene pedidos históricos. */
export interface ProductDeleteImpact {
  impacted_orders: number;
}

/** POST /pricing/preview — línea del preview en vivo (contrato Fase 4). */
export interface PreviewLineItem {
  qty: number;
  unit: string;
  price_per_purchase_unit: number;
  purchase_unit: string;
}

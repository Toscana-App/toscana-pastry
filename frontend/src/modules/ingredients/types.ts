
export const INGREDIENT_UNITS = ["kg", "g", "L", "ml", "unidad"] as const;
export type IngredientUnit = (typeof INGREDIENT_UNITS)[number];

export const STOCK_REASONS = ["compra", "merma", "ajuste"] as const;
export type StockReason = (typeof STOCK_REASONS)[number];

export type IngredientStatus = "OK" | "LOW" | "EMPTY";

export interface Ingredient {
  id: string;
  name: string;
  unit: IngredientUnit;
  price_per_unit: number;
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

export interface IngredientListParams {
  q?: string;
  status?: IngredientStatus;
  page?: number;
  page_size?: number;
}

export interface StockMovement {
  id: string;
  qty_delta: string;
  reason: string;
  ref: string | null;
  created_at: string;
}

export interface IngredientDetailResponse {
  ingredient: Ingredient;
  movements: StockMovement[] | null;
}

export interface IngredientCreateInput {
  name: string;
  unit: IngredientUnit;
  price_per_unit: number;
  stock_qty: number;
  low_stock_threshold: number;
}

export type IngredientUpdateInput = Partial<
  Pick<
    IngredientCreateInput,
    "name" | "unit" | "price_per_unit" | "low_stock_threshold"
  >
>;

export interface StockAdjustInput {
  delta: number;
  reason: StockReason;
  ref?: string;
}

export interface StockAdjustmentResponse {
  stock_qty: string;
  movement: StockMovement;
}

export interface ImportErrorItem {
  line: number;
  message: string;
}

export interface ImportResponse {
  created: number;
  errors: ImportErrorItem[];
}

export interface DeleteImpact {
  impacted_recipes: number;
}

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

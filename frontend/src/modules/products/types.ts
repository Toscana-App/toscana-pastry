
export const PRODUCT_DIFFICULTIES = ["simple", "intermedio", "complejo"] as const;
export type ProductDifficulty = (typeof PRODUCT_DIFFICULTIES)[number];

export const RECIPE_UNITS = ["kg", "g", "L", "ml", "unidad"] as const;
export type RecipeUnit = (typeof RECIPE_UNITS)[number];

export interface ProductListItem {
  id: string;
  name: string;
  category: string;
  price_final: number | null;
  price_per_serving: number | null;
  complete: boolean;
  available: boolean;
  image_url: string | null;
}

export interface ProductListResponse {
  items: ProductListItem[];
  total: number;
  page: number;
  page_size: number;
  categories: string[];
}

export interface ProductListParams {
  q?: string;
  category?: string;
  page?: number;
  page_size?: number;
}

export interface PriceBreakdown {
  materials: number;
  waste: number;
  materials_con_merma: number;
  labor: number;
  gas: number;
  base: number;
  margin_pct: string;
  final: number;
  rounded: number;
}

export interface RecipeItemDetail {
  ingredient_id: string;
  ingredient_name: string;
  qty: string;
  unit: string;
  purchase_unit: string | null;
  price_per_unit: number | null;
  line_cost: number | null;
  missing: boolean;
}

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
  available: boolean;
  image_url: string | null;
  price: PriceBreakdown | null;
  price_per_serving: number | null;
  recipe: RecipeItemDetail[];
}

export interface RecipeItemInput {
  ingredient_id: string;
  qty: number;
  unit: RecipeUnit;
}

export interface ProductCreateInput {
  name: string;
  category: string;
  description?: string;
  prep_time_min?: number;
  servings?: number;
  difficulty?: ProductDifficulty;
  recipe: RecipeItemInput[];
}

export interface ProductUpdateInput
  extends Partial<Omit<ProductCreateInput, "recipe">> {
  recipe?: RecipeItemInput[];
  available?: boolean;
}

export interface ProductImageResponse {
  image_url: string;
}

export interface ProductDeleteImpact {
  impacted_orders: number;
}

export interface PreviewLineItem {
  qty: number;
  unit: string;
  price_per_purchase_unit: number;
  purchase_unit: string;
}

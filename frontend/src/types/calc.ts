
export type RoundingMode =
  | "none"
  | "integer"
  | "multiple_10"
  | "commercial_99";

export interface CalcSettingsResponse {
  business_name: string;
  main_currency_name: string;
  main_currency_symbol: string;
  default_margin_percent: string;
  default_discount_percent: string;
  default_tax_percent: string;
  rounding_mode: RoundingMode;
}

export type CalcSettingsPayload = CalcSettingsResponse;

export type CategoryKind = "material-categories" | "product-categories";

export interface Category {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryListResponse {
  items: Category[];
  total: number;
  page: number;
  page_size: number;
}

export interface CategoryCreatePayload {
  name: string;
  description?: string;
}

export interface CategoryUpdatePayload {
  name?: string;
  description?: string | null;
}

export interface Supplier {
  id: string;
  name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierListResponse {
  items: Supplier[];
  total: number;
  page: number;
  page_size: number;
}

export interface SupplierCreatePayload {
  name: string;
  contact_name?: string;
  phone?: string;
  email?: string;
  notes?: string;
}

export interface SupplierUpdatePayload {
  name?: string;
  contact_name?: string | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
}

export type DefaultCostType = "labor" | "extra_cost";
export type DefaultCostStatus = "active" | "inactive";

export interface DefaultCost {
  id: string;
  name: string;
  type: DefaultCostType;
  default_unit_cost_or_rate: string;
  default_quantity_or_minutes: string;
  status: DefaultCostStatus;
  created_at: string;
  updated_at: string;
}

export interface DefaultCostListResponse {
  items: DefaultCost[];
  total: number;
  page: number;
  page_size: number;
}

export interface DefaultCostCreatePayload {
  name: string;
  type: DefaultCostType;
  default_unit_cost_or_rate: string;
  default_quantity_or_minutes: string;
  status?: DefaultCostStatus;
}

export interface DefaultCostUpdatePayload {
  name?: string;
  type?: DefaultCostType;
  default_unit_cost_or_rate?: string;
  default_quantity_or_minutes?: string;
  status?: DefaultCostStatus;
}

export type MaterialStatus = "active" | "incomplete";
export type ProductStatus = "draft" | "active" | "archived";

export type ProductLineMaterialIn = {
  material_id: string;
  quantity_used: string;
};

export type ProductLineLaborIn = {
  activity_name: string;
  hourly_rate: string;
  minutes_required: string;
};

export type ProductLineExtraCostIn = {
  concept_name: string;
  unit_cost: string;
  quantity: string;
};

export type ProductLineMaterialOut = {
  material_id: string;
  material_name: string;
  quantity_used: string;
  unit_of_measure_snapshot: string | null;
  unit_cost_snapshot: number;
  line_total_cost: number;
  sort_order: number;
};

export type ProductLineLaborOut = {
  activity_name: string;
  hourly_rate: number;
  minutes_required: string;
  line_total_cost: number;
  sort_order: number;
};

export type ProductLineExtraCostOut = {
  concept_name: string;
  unit_cost: number;
  quantity: string;
  line_total_cost: number;
  sort_order: number;
};

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  category_id: string | null;
  description: string | null;
  notes: string | null;
  margin_percent: string;
  discount_percent: string;
  tax_percent: string;
  status: ProductStatus;
  last_recalculated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductListItem {
  id: string;
  name: string;
  sku: string | null;
  category_name: string | null;
  status: ProductStatus;
  product_total_cost: number;
  final_sale_price: number;
  margin_percent: string;
  last_recalculated_at: string | null;
}

export interface ProductListResponse {
  items: ProductListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProductCostsResponse {
  product_total_cost: number;
  profit_amount: number;
  discount_amount: number;
  adjusted_profit_amount: number;
  tax_amount: number;
  final_sale_price: number;
}

export interface ProductWithLines {
  product: Product;
  product_lines: {
    materials: ProductLineMaterialOut[];
    labor: ProductLineLaborOut[];
    extra_costs: ProductLineExtraCostOut[];
  };
  costs: ProductCostsResponse;
}

export interface ProductDetail {
  product: Product;
  materials: ProductLineMaterialOut[];
  labor: ProductLineLaborOut[];
  extra_costs: ProductLineExtraCostOut[];
  costs: ProductCostsResponse;
}

export interface ProductVersion {
  version_number: number;
  product_total_cost: number;
  profit_amount: number;
  discount_amount: number;
  adjusted_profit_amount: number;
  tax_amount: number;
  final_sale_price: number;
  changed_at: string;
}

export interface ProductVersionListResponse {
  items: ProductVersion[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProductListQuery {
  q?: string;
  category_id?: string;
  status?: ProductStatus;
  page?: number;
  page_size?: number;
  sort?: "name" | "cost" | "price" | "margin";
  dir?: "asc" | "desc";
}

export type PriceListItem = {
  id: string;
  name: string;
  sku: string | null;
  category_id: string | null;
  category_name: string | null;
  product_total_cost: number;
  final_sale_price: number;
  margin_percent: string;
}

export interface PriceListResponse {
  items: PriceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardTopItem {
  id: string;
  name: string;
  final_sale_price: number;
  margin_percent: string;
}

export interface DashboardBottomItem {
  id: string;
  name: string;
  product_total_cost: number;
  margin_percent: string;
}

export interface DashboardResponse {
  active_materials: number;
  active_products: number;
  draft_products: number;
  incomplete_materials: number;
  avg_product_cost: number;
  avg_final_price: number;
  top_by_price: DashboardTopItem[];
  bottom_by_margin: DashboardBottomItem[];
}

export type ProductCreatePayload = {
  name: string;
  sku?: string;
  category_id?: string;
  description?: string;
  notes?: string;
  margin_percent?: string;
  discount_percent?: string;
  tax_percent?: string;
  status?: ProductStatus;
  materials: ProductLineMaterialIn[];
  labor: ProductLineLaborIn[];
  extra_costs: ProductLineExtraCostIn[];
};

export type ProductUpdatePayload = {
  name?: string;
  sku?: string;
  category_id?: string;
  description?: string;
  notes?: string;
  margin_percent?: string;
  discount_percent?: string;
  tax_percent?: string;
  status?: ProductStatus;
  materials?: ProductLineMaterialIn[];
  labor?: ProductLineLaborIn[];
  extra_costs?: ProductLineExtraCostIn[];
};

export interface RecalculateAllResponse {
  recalculated: number;
}

export interface Material {
  id: string;
  name: string;
  internal_code: string | null;
  category_id: string | null;
  supplier_id: string | null;
  unit_of_measure: string | null;
  purchase_total_price: string | null;
  package_quantity: string | null;
  unit_cost: string | null;
  notes: string | null;
  status: MaterialStatus;
  created_at: string;
  updated_at: string;
}

export interface MaterialListResponse {
  items: Material[];
  total: number;
  page: number;
  page_size: number;
}

export interface MaterialCreatePayload {
  name: string;
  internal_code?: string;
  category_id?: string;
  supplier_id?: string;
  unit_of_measure?: string;
  purchase_total_price?: number | null;
  package_quantity?: number | null;
  notes?: string;
}

export interface MaterialUpdatePayload {
  name?: string;
  internal_code?: string | null;
  category_id?: string | null;
  supplier_id?: string | null;
  unit_of_measure?: string | null;
  purchase_total_price?: number | null;
  package_quantity?: number | null;
  notes?: string | null;
}

export interface CostHistoryEntry {
  previous_unit_cost: string | null;
  new_unit_cost: string | null;
  changed_at: string;
}

export interface CostHistoryListResponse {
  items: CostHistoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface MaterialListQuery {
  q?: string;
  category_id?: string;
  supplier_id?: string;
  status?: MaterialStatus;
  page?: number;
  page_size?: number;
}

// Tipos de las respuestas de la API de la calculadora de costos
// (backend/src/api/v1/calc/schemas.py). Los montos y cantidades viajan
// como `string` (serialización de api/v1/money.py): no convertirlos a
// number "para aritmética" (no hay aritmética de precios en F1).

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

// PUT /calc/settings es reemplazo completo atómico (extra="forbid"):
// el payload SIEMPRE lleva los 7 campos, nunca parcial.
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

// PATCH acepta campos opcionales (≥1): mandar solo los tocados.
// description: null limpia la descripción existente.
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

// null limpia el valor existente.
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

// ─── Materials (RF-P2CC-01..05) ──────────────────────────────────────────
// Status 100% derivado por el servidor (decisión D1 de B8): la UI solo lo
// muestra, nunca lo envía. unit_cost es solo-escritura del servidor (RF-P2CC-02).
export type MaterialStatus = "active" | "incomplete";

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

// POST /calc/materials (extra="forbid"): 8 campos; unit_cost/status NUNCA.
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

// PATCH /calc/materials/{id} (exclude_unset): solo campos tocados.
// null en purchase_total_price/package_quantity ELIMINA el dato
// (unit_cost → null, status → incomplete; RF-P2CC-04).
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

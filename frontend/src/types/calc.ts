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

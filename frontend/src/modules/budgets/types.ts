
export const BUDGET_STATUSES = ["borrador", "enviado"] as const;
export type BudgetStatus = (typeof BUDGET_STATUSES)[number];

export const BUDGET_STATUS_LABELS: Record<BudgetStatus, string> = {
  borrador: "Borrador",
  enviado: "Enviado",
};

export const CALCULATION_MODES = ["cost_plus", "manual"] as const;
export type CalculationMode = (typeof CALCULATION_MODES)[number];

export const CALCULATION_MODE_LABELS: Record<CalculationMode, string> = {
  cost_plus: "Costo + margen",
  manual: "Manual",
};

export interface BudgetItemInput {
  product_id: string;
  qty: number;
  price_override: number | null;
}

export interface BudgetCreatePayload {
  customer_id: string;
  calculation_mode: CalculationMode;
  margin_pct: string | null;
  delivery_address?: string | null;
  items: BudgetItemInput[];
}

export interface BudgetUpdatePayload {
  customer_id?: string;
  calculation_mode?: CalculationMode;
  margin_pct?: string | null;
  items?: BudgetItemInput[];
}

export interface BudgetListItem {
  id: string;
  seq: string;
  customer_name: string;
  customer_phone: string;
  status: BudgetStatus;
  item_count: number;
  total: number;
  version: number;
  created_at: string;
  sent_at: string | null;
}

export interface BudgetListResponse {
  items: BudgetListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface BudgetListParams {
  q?: string;
  status?: BudgetStatus;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
}

export type ExportFormat = "csv" | "pdf";

export type BudgetExportParams = Pick<BudgetListParams, "status" | "from" | "to">;

export interface BudgetItem {
  product_id: string;
  product_name: string;
  qty: number;
  unit_cost: number;
  unit_selling: number;
  line_cost: number;
  line_selling: number;
  price_overridden: boolean;
}

export interface BudgetSummary {
  subtotal: number;
  total_costos: number;
  ganancia: number;
  total_venta: number;
  iva: number;
}

export interface BudgetCustomer {
  id: string;
  name: string;
  phone: string;
}

export interface BudgetDetail {
  id: string;
  seq: string;
  customer: BudgetCustomer;
  status: BudgetStatus;
  calculation_mode: CalculationMode;
  margin_pct: number | null;
  version: number;
  items: BudgetItem[];
  summary: BudgetSummary;
  delivery_address: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
}

export interface RecalculateResponse {
  summary: BudgetSummary;
  margin_applied: number;
}

export interface ConvertToOrderResponse {
  order_id: string;
  seq: string;
}

export interface PdfShare {
  url: string;
  expires_at: string;
}

export interface WhatsAppLink {
  url: string;
  sent_at: string;
}

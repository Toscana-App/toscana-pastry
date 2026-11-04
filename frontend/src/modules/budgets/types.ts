/**
 * Tipos del módulo de presupuestos (Fase 7, P7/P8) — espejo del contrato
 * `backend/src/api/v1/budgets/schemas.py` (docs/specs/p07+p08).
 *
 * Regla de montos: la API emite TODO monto como `long` de centavos (int)
 * (RF-P8-03); los componentes solo ven centavos y formatean con
 * `formatCents`. `margin_pct` es un PORCENTAJE (0-200), viaja como string
 * numérico y el service lo convierte a `number` plano (100 = 100%).
 */

/** Estados del presupuesto (RF-P8-05). */
export const BUDGET_STATUSES = ["borrador", "enviado"] as const;
export type BudgetStatus = (typeof BUDGET_STATUSES)[number];

export const BUDGET_STATUS_LABELS: Record<BudgetStatus, string> = {
  borrador: "Borrador",
  enviado: "Enviado",
};

/** Modos de cálculo (RF-P7-05 / RF-P8-02). */
export const CALCULATION_MODES = ["cost_plus", "manual"] as const;
export type CalculationMode = (typeof CALCULATION_MODES)[number];

export const CALCULATION_MODE_LABELS: Record<CalculationMode, string> = {
  cost_plus: "Costo + margen",
  manual: "Manual",
};

/** Línea del wizard. `price_override` solo aplica en modo manual (centavos). */
export interface BudgetItemInput {
  product_id: string;
  qty: number;
  /** null = costo + margen (o sin override en manual). En centavos. */
  price_override: number | null;
}

/** POST /budgets — payload del wizard completo (P7). */
export interface BudgetCreatePayload {
  customer_id: string;
  calculation_mode: CalculationMode;
  /** null = margen del tenant. */
  margin_pct: string | null;
  /** Snapshot de la dirección de entrega (Fase 7, RF-P7-06). */
  delivery_address?: string | null;
  items: BudgetItemInput[];
}

/** PUT /budgets/{id} — parcial (borrador y enviado, reenviar). */
export interface BudgetUpdatePayload {
  customer_id?: string;
  calculation_mode?: CalculationMode;
  margin_pct?: string | null;
  items?: BudgetItemInput[];
}

/** GET /budgets — ítem del listado (RF-P8-06). */
export interface BudgetListItem {
  id: string;
  seq: string;
  customer_name: string;
  customer_phone: string;
  status: BudgetStatus;
  item_count: number;
  /** Subtotal de venta (sin IVA), en centavos. */
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

/** Filtros combinables del listado. */
export interface BudgetListParams {
  q?: string;
  status?: BudgetStatus;
  /** YYYY-MM-DD (alias `from` en el wire). */
  from?: string;
  /** YYYY-MM-DD (alias `to` en el wire). */
  to?: string;
  page?: number;
  page_size?: number;
}

/** Formato de exportación (Fase 5): CSV por defecto, PDF opcional. */
export type ExportFormat = "csv" | "pdf";

/** GET /budgets/export — filtros del export (mismos que el listado). */
export type BudgetExportParams = Pick<BudgetListParams, "status" | "from" | "to">;

/** Línea del presupuesto — costos y precio guardados al escribir. */
export interface BudgetItem {
  product_id: string;
  product_name: string;
  qty: number;
  /** Costo por unidad en centavos (snapshot del catálogo al guardar). */
  unit_cost: number;
  /** Precio de venta por unidad en centavos. */
  unit_selling: number;
  /** qty × unit_cost. */
  line_cost: number;
  /** qty × unit_selling. */
  line_selling: number;
  /** true → el precio vino como override manual, no del motor. */
  price_overridden: boolean;
}

/** Totales del presupuesto (RF-P8-02) — todo en centavos. */
export interface BudgetSummary {
  /** Σ qty × unit_selling (sin IVA). */
  subtotal: number;
  /** Σ qty × unit_cost. */
  total_costos: number;
  /** subtotal − total_costos (puede ser negativa). */
  ganancia: number;
  /** subtotal + IVA 21%. */
  total_venta: number;
}

export interface BudgetCustomer {
  id: string;
  name: string;
  phone: string;
}

/** GET /budgets/{id} — detalle. */
export interface BudgetDetail {
  id: string;
  seq: string;
  customer: BudgetCustomer;
  status: BudgetStatus;
  calculation_mode: CalculationMode;
  /** null = margen del tenant. En porcentaje (0-200). */
  margin_pct: number | null;
  version: number;
  items: BudgetItem[];
  summary: BudgetSummary;
  /** Snapshot de la dirección de entrega (Fase 7, RF-P7-07). */
  delivery_address: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
}

/** POST /budgets/{id}/recalculate — respuesta. */
export interface RecalculateResponse {
  summary: BudgetSummary;
  /** Margen aplicado (override o tenant), en porcentaje. */
  margin_applied: number;
}

/** POST /budgets/{id}/convert-to-order — respuesta. */
export interface ConvertToOrderResponse {
  order_id: string;
  /** Secuencia del presupuesto (para el log). */
  seq: string;
}

/** POST /budgets/{id}/pdf (P9): link firmado temporal de 72 h. */
export interface PdfShare {
  url: string;
  /** ISO 8601 UTC. */
  expires_at: string;
}

/** POST /budgets/{id}/whatsapp-link (P10): wa.me prellenado. */
export interface WhatsAppLink {
  url: string;
  /** Momento del registro de auditoría (RF-P10-02). ISO 8601 UTC. */
  sent_at: string;
}

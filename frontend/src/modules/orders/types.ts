/**
 * Tipos del módulo de pedidos (Fase 6, P6) — espejo del contrato
 * `backend/src/api/v1/orders/schemas.py` (docs/specs/p06_orders.md).
 *
 * Regla de montos: la API emite TODO monto como `long` de centavos (int); los
 * componentes solo ven centavos y formatean con `formatCents`.
 * `available`/`required` del 409 son Qty (cantidades), no dinero.
 *
 * Excepción: `margin_pct` es un PORCENTAJE (0-200, mismo rango que el motor),
 * no un monto: viaja como string numérico y el service lo convierte a
 * `number` plano (100 = 100%). Se formatea con `formatPct`.
 */

/** Estados del pedido (RNF-P6-01). */
export const ORDER_STATUSES = ["nuevo", "confirmado", "entregado", "cancelado"] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

/** Rótulos en español para la UI (la API viaja con los códigos). */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  nuevo: "Nuevo",
  confirmado: "Confirmado",
  entregado: "Entregado",
  cancelado: "Cancelado",
};

/**
 * Transiciones válidas (RNF-P6-01):
 * nuevo→confirmado→entregado; cancelado solo desde confirmado.
 */
export const ALLOWED_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  nuevo: ["confirmado"],
  confirmado: ["entregado", "cancelado"],
  entregado: [],
  cancelado: [],
};

/** Línea del wizard: `portions` ausente = porciones del producto. */
export interface OrderItemInput {
  product_id: string;
  qty: number;
  /** null = porciones del producto (factor de escalado 1). */
  portions: number | null;
  note: string;
}

/** POST /orders — payload del wizard (UC-02). */
export interface OrderCreatePayload {
  customer_id: string;
  date: string; // YYYY-MM-DD
  /** null = margen del tenant. */
  margin_pct: string | null;
  items: OrderItemInput[];
}

/** PATCH /orders/{id} — parcial, solo estado nuevo. */
export type OrderUpdatePayload = Partial<Omit<OrderCreatePayload, "date">> & {
  date?: string;
};

/** GET /orders — ítem del listado (UC-01). */
export interface OrderListItem {
  id: string;
  customer_name: string;
  customer_phone: string;
  date: string; // YYYY-MM-DD
  status: OrderStatus;
  item_count: number;
  /** Total del pedido en centavos (long). */
  total: number;
  created_at: string;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
}

/** Filtros combinables del listado (RF-P6-05). */
export interface OrderListParams {
  status?: OrderStatus;
  customer_id?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

/** Desglose congelado en el snapshot (RNF-P6-03) — todo en centavos. */
export interface OrderItemBreakdown {
  materials: number;
  waste: number;
  materials_con_merma: number;
  labor: number;
  gas: number;
  base: number;
  /** Margen aplicado a esta línea, en porcentaje (0-200). */
  margin_pct: number;
  final: number;
  rounded: number;
}

/** Línea de insumo del snapshot — qty es cantidad (string), cost en centavos. */
export interface SnapshotLine {
  ingredient_id: string;
  ingredient_name: string;
  qty: string;
  unit: string;
  cost: number;
  /** true → insumo sin precio o borrado: costo 0, marca la incompletitud. */
  is_missing: boolean;
}

/** Ítem del pedido (detalle) — snapshot inmutable (RNF-P6-03). */
export interface OrderItem {
  product_id: string;
  product_name: string;
  qty: number;
  portions: number;
  note: string;
  /** false → alguna línea tiene insumo sin precio. */
  complete: boolean;
  /** Nombres de los insumos faltantes (para la UI de advertencia). */
  missing_ingredients: string[];
  price: OrderItemBreakdown;
  lines: SnapshotLine[];
  /** Precio redondeado por el motor, en centavos. */
  rounded: number;
}

export interface OrderCustomer {
  id: string;
  name: string;
  phone: string;
}

/** GET /orders/{id} — detalle (UC-03). */
export interface OrderDetail {
  id: string;
  customer: OrderCustomer;
  date: string;
  status: OrderStatus;
  /** null = se usó el margen del tenant. En porcentaje (0-200). */
  margin_pct: number | null;
  items: OrderItem[];
  /** Total del pedido en centavos. */
  total: number;
  whatsapp_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /orders/preview — ítem cotizado en vivo (UC-02). */
export interface OrderPreviewItem {
  product_id: string;
  product_name: string;
  qty: number;
  portions: number;
  complete: boolean;
  missing_ingredients: string[];
  price: OrderItemBreakdown;
  lines: SnapshotLine[];
  rounded: number;
}

/** POST /orders/preview — respuesta de la cotización en vivo. */
export interface OrderPreviewResponse {
  /** Margen aplicado (override o tenant), en porcentaje (0-200). */
  margin_pct: number;
  /** Margen del tenant (para mostrar cuando no hay override). */
  tenant_margin_pct: number;
  items: OrderPreviewItem[];
  total: number;
}

/** 409 al confirmar: stock insuficiente — nada se descuenta (RNF-P6-04). */
export interface InsufficientStockItem {
  ingredient_id: string;
  ingredient_name: string;
  available: number;
  required: number;
}

export interface InsufficientStockResponse {
  insufficient_stock: InsufficientStockItem[];
}

/** POST /orders/{id}/whatsapp-link — enlace generado (UC-05). */
export interface WhatsAppLink {
  url: string;
  message: string;
}

/** POST /customers — alta/dedupe (X-05). 409 → `existing`. */
export interface Customer {
  id: string;
  name: string;
  phone: string;
  /** null = sin dirección de entrega (Fase 7, RF-P7-03). */
  delivery_address?: string | null;
}

export interface CustomerCreateInput {
  name: string;
  phone: string;
  /** Opcional: se guarda en el cliente (Fase 7, RF-P7-06). */
  delivery_address?: string | null;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

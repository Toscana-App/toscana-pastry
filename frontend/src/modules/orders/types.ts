
export const ORDER_STATUSES = ["nuevo", "confirmado", "entregado", "cancelado"] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  nuevo: "Nuevo",
  confirmado: "Confirmado",
  entregado: "Entregado",
  cancelado: "Cancelado",
};

export const ALLOWED_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  nuevo: ["confirmado"],
  confirmado: ["entregado", "cancelado"],
  entregado: [],
  cancelado: [],
};

export interface OrderItemInput {
  product_id: string;
  qty: number;
  portions: number | null;
  note: string;
}

export interface OrderCreatePayload {
  customer_id: string;
  date: string;
  margin_pct: string | null;
  items: OrderItemInput[];
}

export type OrderUpdatePayload = Partial<Omit<OrderCreatePayload, "date">> & {
  date?: string;
};

export interface OrderListItem {
  id: string;
  customer_name: string;
  customer_phone: string;
  date: string;
  status: OrderStatus;
  item_count: number;
  total: number;
  paid: boolean;
  created_at: string;
}

export interface WeeklyRange {
  from: string;
  to: string;
}

export interface WeeklyItem {
  id: string;
  customer: string;
  date: string;
  items_count: number;
  total: number;
  paid: boolean;
  payment_method: string;
}

export interface WeeklyTotals {
  amount: number;
  paid: number;
  unpaid: number;
}

export interface WeeklySummary {
  week: WeeklyRange;
  items: WeeklyItem[];
  totals: WeeklyTotals;
}

export type ExportFormat = "csv" | "pdf";

export interface OrderExportParams {
  status?: OrderStatus;
  paid?: boolean;
  from?: string;
  to?: string;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface OrderListParams {
  status?: OrderStatus;
  customer_id?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  paid?: boolean;
  page?: number;
  page_size?: number;
}

export interface OrderItemBreakdown {
  materials: number;
  waste: number;
  materials_con_merma: number;
  labor: number;
  gas: number;
  base: number;
  margin_pct: number;
  final: number;
  rounded: number;
}

export interface SnapshotLine {
  ingredient_id: string;
  ingredient_name: string;
  qty: string;
  unit: string;
  cost: number;
  is_missing: boolean;
}

export interface OrderItem {
  product_id: string;
  product_name: string;
  qty: number;
  portions: number;
  note: string;
  complete: boolean;
  missing_ingredients: string[];
  price: OrderItemBreakdown;
  lines: SnapshotLine[];
  rounded: number;
}

export interface OrderCustomer {
  id: string;
  name: string;
  phone: string;
}

export interface OrderDetail {
  id: string;
  customer: OrderCustomer;
  date: string;
  status: OrderStatus;
  margin_pct: number | null;
  items: OrderItem[];
  total: number;
  paid: boolean;
  whatsapp_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

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

export interface OrderPreviewResponse {
  margin_pct: number;
  tenant_margin_pct: number;
  items: OrderPreviewItem[];
  total: number;
}

export interface InsufficientStockItem {
  ingredient_id: string;
  ingredient_name: string;
  available: number;
  required: number;
}

export interface InsufficientStockResponse {
  insufficient_stock: InsufficientStockItem[];
}

export interface WhatsAppLink {
  url: string;
  message: string;
}

export interface Customer {
  id: string;
  name: string;
  phone: string;
  delivery_address?: string | null;
}

export interface CustomerCreateInput {
  name: string;
  phone: string;
  delivery_address?: string | null;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

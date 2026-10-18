import { apiFetch, ApiError } from "@/lib/api";
import { moneyToCents } from "@/lib/format";
import type {
  Customer,
  CustomerCreateInput,
  CustomerListResponse,
  InsufficientStockResponse,
  OrderCreatePayload,
  OrderDetail,
  OrderItemBreakdown,
  OrderListParams,
  OrderListResponse,
  OrderPreviewItem,
  OrderPreviewResponse,
  OrderStatus,
  OrderUpdatePayload,
  OrderItem,
  SnapshotLine,
  WhatsAppLink,
} from "./types";

const BASE = "/orders";
const CUSTOMERS = "/customers";

/**
 * Servicio tipado de pedidos (Fase 6, P6): espejo 1:1 del contrato
 * `backend/src/api/v1/orders/schemas.py` (docs/specs/p06_orders.md).
 *
 * Regla de montos: la API emite Money como string (RNF-P4-02); el service lo
 * convierte a `long` de centavos (últimos 2 dígitos = centavos) al recibir.
 * Los componentes solo ven centavos. En las requests el margen viaja como
 * string numérico (el backend lo parsea a Decimal).
 *
 * RBAC (backend): listado/lectura para todo usuario autenticado; create,
 * preview, update, status y whatsapp solo admin.
 */

function breakdownOf(raw: Record<string, unknown>): OrderItemBreakdown {
  const b = raw as unknown as Record<string, string>;
  return {
    materials: moneyToCents(b.materials),
    waste: moneyToCents(b.waste),
    materials_con_merma: moneyToCents(b.materials_con_merma),
    labor: moneyToCents(b.labor),
    gas: moneyToCents(b.gas),
    base: moneyToCents(b.base),
    margin_pct: Number(b.margin_pct),
    final: moneyToCents(b.final),
    rounded: moneyToCents(b.rounded),
  };
}

function linesOf(raws: unknown[]): SnapshotLine[] {
  return raws.map((raw) => {
    const l = raw as Record<string, unknown> & { ingredient_id: string; ingredient_name: string; qty: string; unit: string; is_missing?: boolean };
    return {
      ingredient_id: l.ingredient_id,
      ingredient_name: l.ingredient_name,
      qty: l.qty,
      unit: l.unit,
      cost: moneyToCents(l.cost as string),
      is_missing: l.is_missing ?? false,
    };
  });
}

function orderItemOf(raw: Record<string, unknown>): OrderItem {
  return {
    product_id: raw.product_id as string,
    product_name: raw.product_name as string,
    qty: raw.qty as number,
    portions: raw.portions as number,
    note: raw.note as string,
    complete: raw.complete as boolean,
    missing_ingredients: raw.missing_ingredients as string[],
    price: breakdownOf(raw.price as Record<string, unknown>),
    lines: linesOf(raw.lines as unknown[]),
    rounded: moneyToCents(raw.rounded as string),
  };
}

function previewItemOf(raw: Record<string, unknown>): OrderPreviewItem {
  return {
    product_id: raw.product_id as string,
    product_name: raw.product_name as string,
    qty: raw.qty as number,
    portions: raw.portions as number,
    complete: raw.complete as boolean,
    missing_ingredients: raw.missing_ingredients as string[],
    price: breakdownOf(raw.price as Record<string, unknown>),
    lines: linesOf(raw.lines as unknown[]),
    rounded: moneyToCents(raw.rounded as string),
  };
}

function detailOf(raw: Record<string, unknown>): OrderDetail {
  const customer = raw.customer as Record<string, unknown>;
  return {
    id: raw.id as string,
    customer: {
      id: customer.id as string,
      name: customer.name as string,
      phone: customer.phone as string,
    },
    date: raw.date as string,
    status: raw.status as OrderStatus,
    margin_pct: raw.margin_pct == null ? null : Number(raw.margin_pct as string),
    items: (raw.items as unknown[]).map((i) => orderItemOf(i as Record<string, unknown>)),
    total: moneyToCents(raw.total as string),
    whatsapp_sent_at: raw.whatsapp_sent_at as string | null,
    created_at: raw.created_at as string,
    updated_at: raw.updated_at as string,
  };
}

export const ordersService = {
  /**
   * GET /orders — listado con filtros combinables (RF-P6-05): estado,
   * cliente, nombre (q) y rango de fechas. Paginado (20 por página).
   */
  list(params: OrderListParams = {}): Promise<OrderListResponse> {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.customer_id) query.set("customer_id", params.customer_id);
    if (params.q) query.set("q", params.q);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<OrderListResponse>(`${BASE}${qs ? `?${qs}` : ""}`).then((res) => ({
      ...res,
      items: res.items.map((i) => ({ ...i, total: moneyToCents(i.total) })),
    }));
  },

  /** GET /orders/{id} — detalle con snapshot congelado (RNF-P6-03). */
  getDetail(id: string): Promise<OrderDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`).then(detailOf);
  },

  /**
   * POST /orders — crea el pedido (UC-02). 201 → detalle.
   * 409 → stock insuficiente al confirmar (nada se descuenta, RNF-P6-04):
   * llega como ApiError con payload `{insufficient_stock}`.
   */
  create(payload: OrderCreatePayload): Promise<OrderDetail> {
    return apiFetch<Record<string, unknown>>(BASE, {
      method: "POST",
      body: JSON.stringify({
        customer_id: payload.customer_id,
        date: payload.date,
        margin_pct: payload.margin_pct,
        items: payload.items.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          ...(i.portions != null ? { portions: i.portions } : {}),
          note: i.note,
        })),
      }),
    }).then(detailOf);
  },

  /** PATCH /orders/{id} — edición parcial, solo estado nuevo. 409 si no. */
  update(id: string, payload: OrderUpdatePayload): Promise<OrderDetail> {
    const body: Record<string, unknown> = {};
    if (payload.customer_id != null) body.customer_id = payload.customer_id;
    if (payload.date != null) body.date = payload.date;
    if (payload.margin_pct != null) body.margin_pct = payload.margin_pct;
    if (payload.items != null) {
      body.items = payload.items.map((i) => ({
        product_id: i.product_id,
        qty: i.qty,
        ...(i.portions != null ? { portions: i.portions } : {}),
        note: i.note,
      }));
    }
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }).then(detailOf);
  },

  /**
   * PATCH /orders/{id}/status — transición (RNF-P6-01). Confirmar descuenta
   * stock atómicamente: 409 con `{insufficient_stock}` y cero cambios.
   */
  changeStatus(id: string, status: OrderStatus): Promise<OrderDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }).then(detailOf);
  },

  /**
   * POST /orders/preview — cotización en vivo del wizard (admin, sin
   * persistir). Mismo cálculo que el create.
   */
  preview(items: OrderCreatePayload["items"], marginPct: string | null): Promise<OrderPreviewResponse> {
    return apiFetch<Record<string, unknown>>(`${BASE}/preview`, {
      method: "POST",
      body: JSON.stringify({
        margin_pct: marginPct,
        items: items.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          ...(i.portions != null ? { portions: i.portions } : {}),
          note: i.note,
        })),
      }),
    }).then((raw) => ({
      margin_pct: Number(raw.margin_pct as string),
      tenant_margin_pct: Number(raw.tenant_margin_pct as string),
      items: (raw.items as unknown[]).map((i) => previewItemOf(i as Record<string, unknown>)),
      total: moneyToCents(raw.total as string),
    }));
  },

  /** POST /orders/{id}/whatsapp — enlace wa.me con el mensaje del pedido. */
  whatsapp(id: string): Promise<WhatsAppLink> {
    return apiFetch<WhatsAppLink>(`${BASE}/${id}/whatsapp`, { method: "POST" });
  },
};

/**
 * Servicio de clientes (Fase 6, X-05): alta con dedupe por nombre+teléfono.
 * 409 → el cliente ya existe; el backend lo devuelve en `existing` (y en la
 * header X-Customer-Id): la UI lo usa en vez de mostrar un error.
 */
export const customersService = {
  /** GET /customers?q= — búsqueda sin acentos (RF-P2-02), paginada. */
  list(q?: string, page = 1, page_size = 20): Promise<CustomerListResponse> {
    const query = new URLSearchParams();
    if (q) query.set("q", q);
    query.set("page", String(page));
    query.set("page_size", String(page_size));
    return apiFetch<CustomerListResponse>(`${CUSTOMERS}?${query.toString()}`);
  },

  /**
   * POST /customers — 201 → el cliente creado. 409 → devuelve el existente
   * (dedupe) en vez de lanzar: el wizard lo adopta.
   */
  async create(input: CustomerCreateInput): Promise<Customer> {
    try {
      return await apiFetch<Customer>(CUSTOMERS, {
        method: "POST",
        body: JSON.stringify(input),
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const existing = (e.payload as { existing?: Customer } | null)?.existing;
        if (existing) return existing;
      }
      throw e;
    }
  },
};

/** Extrae el detalle de stock insuficiente de un ApiError 409. */
export function insufficientStockOf(error: unknown): InsufficientStockResponse | null {
  if (error instanceof ApiError && error.status === 409) {
    const payload = error.payload as InsufficientStockResponse | null;
    if (payload && Array.isArray(payload.insufficient_stock)) {
      return {
        insufficient_stock: payload.insufficient_stock.map((i) => ({
          ingredient_id: i.ingredient_id,
          ingredient_name: i.ingredient_name,
          available: moneyToCents(i.available),
          required: moneyToCents(i.required),
        })),
      };
    }
  }
  return null;
}

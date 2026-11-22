import { apiFetch, ApiError } from "@/lib/api";
import { downloadEndpoint } from "@/lib/download";
import type {
  Customer,
  CustomerCreateInput,
  CustomerListResponse,
  ExportFormat,
  InsufficientStockResponse,
  OrderCreatePayload,
  OrderDetail,
  OrderExportParams,
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


function breakdownOf(raw: Record<string, unknown>): OrderItemBreakdown {
  return {
    materials: raw.materials as number,
    waste: raw.waste as number,
    materials_con_merma: raw.materials_con_merma as number,
    labor: raw.labor as number,
    gas: raw.gas as number,
    base: raw.base as number,
    margin_pct: Number(raw.margin_pct),
    final: raw.final as number,
    rounded: raw.rounded as number,
  };
}

function linesOf(raws: unknown[]): SnapshotLine[] {
  return raws.map((raw) => {
    const l = raw as {
      ingredient_id: string;
      ingredient_name: string;
      qty: string;
      unit: string;
      cost: number;
      is_missing?: boolean;
    };
    return {
      ingredient_id: l.ingredient_id,
      ingredient_name: l.ingredient_name,
      qty: l.qty,
      unit: l.unit,
      cost: l.cost,
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
    rounded: raw.rounded as number,
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
    rounded: raw.rounded as number,
  };
}

function detailOf(raw: Record<string, unknown>): OrderDetail {
  const customer = raw.customer as Record<string, unknown>;
  const rawInvoice = raw.invoice as Record<string, unknown> | null;
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
    total: raw.total as number,
    paid: Boolean(raw.paid),
    whatsapp_sent_at: raw.whatsapp_sent_at as string | null,
    created_at: raw.created_at as string,
    updated_at: raw.updated_at as string,
    invoice: rawInvoice == null
      ? null
      : {
          numero: Number(rawInvoice.numero),
          cae: rawInvoice.cae as string,
          cae_vto: rawInvoice.cae_vto as string,
          pdf_url: rawInvoice.pdf_url as string,
        },
  };
}

export const ordersService = {
  list(params: OrderListParams = {}): Promise<OrderListResponse> {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.customer_id) query.set("customer_id", params.customer_id);
    if (params.q) query.set("q", params.q);
    if (params.date_from) query.set("date_from", params.date_from);
    if (params.date_to) query.set("date_to", params.date_to);
    if (params.paid != null) query.set("paid", String(params.paid));
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<OrderListResponse>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  getDetail(id: string): Promise<OrderDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`).then(detailOf);
  },

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

  update(id: string, payload: OrderUpdatePayload): Promise<OrderDetail> {
    const body: Record<string, unknown> = {};
    if (payload.customer_id != null) body.customer_id = payload.customer_id;
    if (payload.date != null) body.date = payload.date;
    if (payload.margin_pct !== undefined) body.margin_pct = payload.margin_pct;
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

  changeStatus(id: string, status: OrderStatus): Promise<OrderDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }).then(detailOf);
  },

  markPaid(id: string): Promise<{ id: string; paid: boolean }> {
    return apiFetch<{ id: string; paid: boolean }>(`${BASE}/${id}/paid`, {
      method: "PATCH",
      body: JSON.stringify({}),
    });
  },

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
      total: raw.total as number,
    }));
  },

  whatsapp(id: string): Promise<WhatsAppLink> {
    return apiFetch<WhatsAppLink>(`${BASE}/${id}/whatsapp-link`, {
      method: "POST",
    });
  },

  exportReport(params: OrderExportParams = {}, format: ExportFormat = "csv"): Promise<void> {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.paid != null) query.set("paid", String(params.paid));
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    query.set("format", format);
    return downloadEndpoint(`${BASE}/export?${query.toString()}`, `pedidos.${format}`);
  },
};

export const customersService = {
  list(q?: string, page = 1, page_size = 20): Promise<CustomerListResponse> {
    const query = new URLSearchParams();
    if (q) query.set("q", q);
    query.set("page", String(page));
    query.set("page_size", String(page_size));
    return apiFetch<CustomerListResponse>(`${CUSTOMERS}?${query.toString()}`);
  },

  async createWithAdoption(
    input: CustomerCreateInput,
  ): Promise<{ customer: Customer; adopted: boolean }> {
    try {
      const customer = await apiFetch<Customer>(CUSTOMERS, {
        method: "POST",
        body: JSON.stringify(input),
      });
      return { customer, adopted: false };
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const existing = (e.payload as { existing?: Customer } | null)?.existing;
        if (existing) return { customer: existing, adopted: true };
      }
      throw e;
    }
  },

  async create(input: CustomerCreateInput): Promise<Customer> {
    const { customer } = await this.createWithAdoption(input);
    return customer;
  },

  updateAddress(id: string, delivery_address: string): Promise<Customer> {
    return apiFetch<Customer>(`${CUSTOMERS}/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ delivery_address }),
    });
  },
};

export function insufficientStockOf(error: unknown): InsufficientStockResponse | null {
  if (error instanceof ApiError && error.status === 409) {
    const payload = error.payload as InsufficientStockResponse | null;
    if (payload && Array.isArray(payload.insufficient_stock)) {
      return {
        insufficient_stock: payload.insufficient_stock.map((i) => ({
          ingredient_id: i.ingredient_id,
          ingredient_name: i.ingredient_name,
          available: Number(i.available),
          required: Number(i.required),
        })),
      };
    }
  }
  return null;
}

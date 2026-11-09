import { apiFetch, ApiError, authorizedFetch } from "@/lib/api";
import { downloadEndpoint } from "@/lib/download";
import type {
  BudgetCreatePayload,
  BudgetDetail,
  BudgetExportParams,
  BudgetItem,
  BudgetListParams,
  BudgetListResponse,
  BudgetSummary,
  BudgetUpdatePayload,
  CalculationMode,
  ConvertToOrderResponse,
  ExportFormat,
  PdfShare,
  RecalculateResponse,
  WhatsAppLink,
} from "./types";

const BASE = "/budgets";


function itemOf(raw: Record<string, unknown>): BudgetItem {
  return {
    product_id: raw.product_id as string,
    product_name: raw.product_name as string,
    qty: raw.qty as number,
    unit_cost: raw.unit_cost as number,
    unit_selling: raw.unit_selling as number,
    line_cost: raw.line_cost as number,
    line_selling: raw.line_selling as number,
    price_overridden: (raw.price_overridden as boolean | undefined) ?? false,
  };
}

function summaryOf(raw: Record<string, unknown>): BudgetSummary {
  return {
    subtotal: raw.subtotal as number,
    total_costos: raw.total_costos as number,
    ganancia: raw.ganancia as number,
    total_venta: raw.total_venta as number,
    iva: raw.iva as number,
  };
}

function detailOf(raw: Record<string, unknown>): BudgetDetail {
  const customer = raw.customer as Record<string, unknown>;
  return {
    id: raw.id as string,
    seq: raw.seq as string,
    customer: {
      id: customer.id as string,
      name: customer.name as string,
      phone: customer.phone as string,
    },
    status: raw.status as BudgetDetail["status"],
    calculation_mode: raw.calculation_mode as CalculationMode,
    margin_pct: raw.margin_pct == null ? null : Number(raw.margin_pct as string),
    version: raw.version as number,
    items: (raw.items as unknown[]).map((i) => itemOf(i as Record<string, unknown>)),
    summary: summaryOf(raw.summary as Record<string, unknown>),
    delivery_address: (raw.delivery_address as string | null) ?? null,
    created_at: raw.created_at as string,
    updated_at: raw.updated_at as string,
    sent_at: raw.sent_at as string | null,
  };
}

export const budgetsService = {
  list(params: BudgetListParams = {}): Promise<BudgetListResponse> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.status) query.set("status", params.status);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<BudgetListResponse>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  getDetail(id: string): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`).then(detailOf);
  },

  create(payload: BudgetCreatePayload): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(BASE, {
      method: "POST",
      body: JSON.stringify({
        customer_id: payload.customer_id,
        calculation_mode: payload.calculation_mode,
        margin_pct: payload.margin_pct,
        ...(payload.delivery_address
          ? { delivery_address: payload.delivery_address }
          : {}),
        items: payload.items.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          ...(i.price_override != null ? { price_override: i.price_override } : {}),
        })),
      }),
    }).then(detailOf);
  },

  update(id: string, payload: BudgetUpdatePayload): Promise<BudgetDetail> {
    const body: Record<string, unknown> = {};
    if (payload.customer_id != null) body.customer_id = payload.customer_id;
    if (payload.calculation_mode != null) body.calculation_mode = payload.calculation_mode;
    if (payload.margin_pct !== undefined) body.margin_pct = payload.margin_pct;
    if (payload.items != null) {
      body.items = payload.items.map((i) => ({
        product_id: i.product_id,
        qty: i.qty,
        ...(i.price_override != null ? { price_override: i.price_override } : {}),
      }));
    }
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }).then(detailOf);
  },

  patchItems(id: string, items: BudgetCreatePayload["items"]): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/items`, {
      method: "PATCH",
      body: JSON.stringify({
        items: items.map((i) => ({
          product_id: i.product_id,
          qty: i.qty,
          ...(i.price_override != null ? { price_override: i.price_override } : {}),
        })),
      }),
    }).then(detailOf);
  },

  recalculate(id: string): Promise<RecalculateResponse> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/recalculate`, {
      method: "POST",
    }).then((raw) => ({
      summary: summaryOf(raw.summary as Record<string, unknown>),
      margin_applied: Number(raw.margin_applied as string),
    }));
  },

  send(id: string): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/send`, {
      method: "POST",
    }).then(detailOf);
  },

  convertToOrder(id: string): Promise<ConvertToOrderResponse> {
    return apiFetch<ConvertToOrderResponse>(`${BASE}/${id}/convert-to-order`, {
      method: "POST",
    });
  },

  remove(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" });
  },

  exportReport(
    params: BudgetExportParams = {},
    format: ExportFormat = "csv",
  ): Promise<void> {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.from) query.set("from", params.from);
    if (params.to) query.set("to", params.to);
    query.set("format", format);
    return downloadEndpoint(`${BASE}/export?${query.toString()}`, `presupuestos.${format}`);  },

  async pdfUrl(id: string): Promise<string> {
    const res = await authorizedFetch(`${BASE}/${id}/pdf`);
    if (!res.ok) throw new ApiError(res.status, "No se pudo generar el PDF");
    return URL.createObjectURL(await res.blob());
  },

  sharePdf(id: string): Promise<PdfShare> {
    return apiFetch<PdfShare>(`${BASE}/${id}/pdf`, { method: "POST" });
  },

  whatsappLink(id: string): Promise<WhatsAppLink> {
    return apiFetch<WhatsAppLink>(`${BASE}/${id}/whatsapp-link`, { method: "POST" });  },
};

import { ACCESS_TOKEN_COOKIE, apiFetch, API_BASE_URL, ApiError } from "@/lib/api";
import { getCookie } from "@/lib/cookies";
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

/**
 * Servicio tipado de presupuestos (Fase 7, P7/P8): espejo 1:1 del contrato
 * `backend/src/api/v1/budgets/schemas.py`.
 *
 * Regla de montos: la API emite centavos (long, RF-P8-03) y recibe centavos;
 * `margin_pct` viaja como string numérico (el backend lo parsea a Decimal).
 * La lectura NUNCA recalcula contra el catálogo: los totales vienen de los
 * items guardados. El presupuesto no toca stock (RNF-P6-02).
 *
 * RBAC (backend): listado/lectura para todo usuario autenticado; create,
 * update, items, recalculate, send, convert-to-order y delete solo admin.
 */

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
  /**
   * GET /budgets — listado con búsqueda (nombre/seq, sin acentos) y filtros
   * de estado y rango de fechas (RF-P8-06). Paginado (20 por página).
   */
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

  /** GET /budgets/{id} — detalle (lectura pura, sin recálculo). */
  getDetail(id: string): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}`).then(detailOf);
  },

  /**
   * POST /budgets — crea el presupuesto en borrador con su secuencia
   * #000NN (UC-03). Los costos se derivan contra el catálogo AHORA.
   */
  create(payload: BudgetCreatePayload): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(BASE, {
      method: "POST",
      body: JSON.stringify({
        customer_id: payload.customer_id,
        calculation_mode: payload.calculation_mode,
        margin_pct: payload.margin_pct,
        // Solo si el wizard la capturó (Fase 7, RF-P7-06); si no, el backend
        // hereda la del cliente.
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

  /** PUT /budgets/{id} — edición parcial (borrador y enviado, RF-P8-05). */
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

  /** PATCH /budgets/{id}/items — reemplaza líneas y recalcula. */
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

  /**
   * POST /budgets/{id}/recalculate — vuelve a derivar los costos contra el
   * catálogo actual (conserva margen y overrides).
   */
  recalculate(id: string): Promise<RecalculateResponse> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/recalculate`, {
      method: "POST",
    }).then((raw) => ({
      summary: summaryOf(raw.summary as Record<string, unknown>),
      margin_applied: Number(raw.margin_applied as string),
    }));
  },

  /**
   * POST /budgets/{id}/send — borrador → enviado (o reenviar tras editar):
   * congela una nueva versión (RF-P8-05). 409 si no hay cambios.
   */
  send(id: string): Promise<BudgetDetail> {
    return apiFetch<Record<string, unknown>>(`${BASE}/${id}/send`, {
      method: "POST",
    }).then(detailOf);
  },

  /**
   * POST /budgets/{id}/convert-to-order — crea el pedido (nuevo) con los
   * mismos ítems y snapshots propios (RF-P8-08). No descuenta stock.
   */
  convertToOrder(id: string): Promise<ConvertToOrderResponse> {
    return apiFetch<ConvertToOrderResponse>(`${BASE}/${id}/convert-to-order`, {
      method: "POST",
    });
  },

  /** DELETE /budgets/{id} — borrado definitivo (no toca stock, RF-P8-07). */
  remove(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" });
  },

  /**
   * GET /budgets/export — descarga binaria del reporte (Fase 5).
   * `format` = "csv" por defecto (backward-compatible) o "pdf".
   * Mismo fetch→blob→download que los exports de pedidos: el filename
   * sale del Content-Disposition del backend.
   */
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

  /**
   * GET /budgets/{id}/pdf (P9) — PDF binario autenticado. Devuelve un
   * objectURL para el preview en página; el llamador revoca el anterior
   * al reemplazarlo. fetch crudo: apiFetch siempre parsea JSON.
   */
  async pdfUrl(id: string): Promise<string> {
    const token = getCookie(ACCESS_TOKEN_COOKIE);
    const res = await fetch(`${API_BASE_URL}${BASE}/${id}/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new ApiError(res.status, "No se pudo generar el PDF");
    return URL.createObjectURL(await res.blob());
  },

  /**
   * POST /budgets/{id}/pdf (P9) — link temporal firmado de 72 h (HMAC,
   * sin sesión): lo abre el cliente final en su navegador.
   */
  sharePdf(id: string): Promise<PdfShare> {
    return apiFetch<PdfShare>(`${BASE}/${id}/pdf`, { method: "POST" });
  },

  /**
   * POST /budgets/{id}/whatsapp-link (P10) — wa.me prellenado con la
   * plantilla + link firmado al PDF. 429 al superar 30 links/día
   * (RNF-P10-06).
   */
  whatsappLink(id: string): Promise<WhatsAppLink> {
    return apiFetch<WhatsAppLink>(`${BASE}/${id}/whatsapp-link`, { method: "POST" });  },
};

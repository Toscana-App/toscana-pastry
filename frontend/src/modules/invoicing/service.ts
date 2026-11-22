import { API_BASE_URL, apiFetch } from "@/lib/api";
import { downloadEndpoint } from "@/lib/download";
import type { Invoice, InvoiceCreatePayload } from "./types";

const BASE = "/invoices";

/**
 * Normaliza un `pdf_url` (relativo, con base API o absoluto) a una ruta relativa
 * a la base API, para poder descargarla con la misma auth por cookie.
 */
function toEndpoint(pdfUrl: string): string {
  let path = pdfUrl;
  if (/^https?:\/\//i.test(pdfUrl)) {
    try {
      path = new URL(pdfUrl).pathname;
    } catch {
      path = pdfUrl;
    }
  }
  const base = new URL(API_BASE_URL).pathname; // p.ej. "/api/v1"
  if (base && base !== "/" && path.startsWith(base)) {
    path = path.slice(base.length);
  }
  if (!path.startsWith("/")) path = `/${path}`;
  return path;
}

function invoiceOf(raw: Record<string, unknown>): Invoice {
  return {
    id: raw.id as string,
    order_id: raw.order_id as string,
    punto_venta: Number(raw.punto_venta),
    tipo_cbte: Number(raw.tipo_cbte),
    numero: Number(raw.numero),
    cae: raw.cae as string,
    cae_vto: raw.cae_vto as string,
    fecha: raw.fecha as string,
    imp_total: Number(raw.imp_total),
    estado: raw.estado as Invoice["estado"],
    pdf_url: raw.pdf_url as string,
  };
}

export const invoicesService = {
  /**
   * Emite el comprobante (POST /api/v1/invoices). Devuelve el comprobante
   * creado. El frontend NO envía montos: el total sale del pedido.
   */
  create(payload: InvoiceCreatePayload): Promise<Invoice> {
    return apiFetch<Record<string, unknown>>(BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then(invoiceOf);
  },

  /**
   * Descarga el PDF del comprobante (GET /api/v1/invoices/{id}/pdf).
   * Usa el `pdf_url` del comprobante (ya sea el de la respuesta 201 o el del
   * detalle del pedido) y lo descarga con la misma auth por cookie.
   */
  downloadPdf(pdfUrl: string, filename = "factura.pdf"): Promise<void> {
    return downloadEndpoint(toEndpoint(pdfUrl), filename);
  },
};

import { apiFetch } from "@/lib/api";
import type {
  PriceBreakdown,
  PreviewLineItem,
  ProductCreateInput,
  ProductDeleteImpact,
  ProductDetail,
  ProductImageResponse,
  ProductListParams,
  ProductListResponse,
  ProductUpdateInput,
} from "./types";

const BASE = "/products";

/**
 * Servicio tipado de productos (Fase 5, P3/P4): espejo 1:1 del contrato
 * `backend/src/api/v1/products/router.py` (docs/specs/phase5-backend.md).
 *
 * - Money/Qty se reciben como string en las responses y se envían como number
 *   en las requests (Pydantic los parsea a Decimal).
 * - El precio nunca se manda: el backend lo deriva en cada lectura (RF-P3-04).
 * - DELETE devuelve 204 No Content (apiFetch ya lo maneja); con pedidos
 *   históricos responde 409 con `{impacted_orders}` (UC-07) — llega como
 *   ApiError con `payload`.
 */
export const productsService = {
  /** GET /products — listado P3 (RF-P3-01/02/03) + categorías derivadas. */
  list(params: ProductListParams = {}): Promise<ProductListResponse> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.category) query.set("category", params.category);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<ProductListResponse>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  /** GET /products/{id} — detalle P4 (receta + desglose o missing). */
  getDetail(id: string): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(`${BASE}/${id}`);
  },

  /** POST /products — alta (RF-P4-01). 201 · 400 receta inválida · 422. */
  create(input: ProductCreateInput): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(BASE, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  /** PATCH /products/{id} — actualización parcial (RF-P4-02). 200 · 400 · 404. */
  update(id: string, input: ProductUpdateInput): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(`${BASE}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  /**
   * DELETE /products/{id} (RF-P4-08): soft delete SIEMPRE — el producto sale
   * del catálogo y los pedidos históricos no se tocan.
   * - 204 → null (no tenía pedidos).
   * - 200 → `{impacted_orders}` (informativo: queda en pedidos históricos).
   */
  remove(id: string): Promise<ProductDeleteImpact | null> {
    return apiFetch<ProductDeleteImpact | void>(`${BASE}/${id}`, {
      method: "DELETE",
    }).then((body) => (body ?? null) as ProductDeleteImpact | null);
  },

  /** POST /products/{id}/image — multipart admin (P12). 201 · 403 · 422 · 413. */
  uploadImage(id: string, file: File): Promise<ProductImageResponse> {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<ProductImageResponse>(`${BASE}/${id}/image`, {
      method: "POST",
      body: form,
    });
  },

  /** DELETE /products/{id}/image — borra la imagen y deja image_url null. */
  removeImage(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}/image`, { method: "DELETE" });
  },

  /**
   * POST /pricing/preview — recálculo en vivo del Costos (RF-P4-04).
   *
   * El motor aplica los settings persistidos del negocio (merma, margen,
   * redondeo). Requiere rol admin (mismo RBAC que el editor). Con líneas de
   * insumos sin precio (0) devuelve el costo parcial, como el detalle.
   */
  preview(
    lineItems: PreviewLineItem[],
    prepMinutes: number,
  ): Promise<PriceBreakdown> {
    return apiFetch<PriceBreakdown>("/pricing/preview", {
      method: "POST",
      body: JSON.stringify({
        line_items: lineItems,
        prep_minutes: prepMinutes,
      }),
    });
  },
};

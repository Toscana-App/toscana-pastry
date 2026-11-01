import { apiFetch } from "@/lib/api";
import type {
  ImportResponse,
  Ingredient,
  IngredientCreateInput,
  IngredientDetailResponse,
  IngredientListParams,
  IngredientUpdateInput,
  Paginated,
  StockAdjustInput,
  StockAdjustmentResponse,
  StockMovement,
} from "./types";

const BASE = "/ingredients";

/**
 * Servcio tipado de ingredientes (Fase 4, WU4): espejo 1:1 del contrato
 * `backend/src/api/v1/ingredients/router.py`.
 *
 * - Money/Qty se reciben como string en las responses y se envían como
 *   number en las requests (Pydantic los parsea a Decimal).
 * - DELETE devuelve 204 No Content; apiFetch ya lo maneja (undefined).
 */
export const ingredientsService = {
  /** GET /ingredients — listado paginado + búsqueda por nombre (RF-P2-01). */
  list(params: IngredientListParams = {}): Promise<Paginated<Ingredient>> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<Paginated<Ingredient>>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  /** GET /ingredients/{id} — detalle; include_movements=true trae el historial. */
  getDetail(
    id: string,
    includeMovements = true,
  ): Promise<IngredientDetailResponse> {
    return apiFetch<IngredientDetailResponse>(
      `${BASE}/${id}?include_movements=${includeMovements ? "true" : "false"}`,
    );
  },

  /** GET /ingredients/{id}/movements — historial paginado. */
  listMovements(id: string, page = 1, pageSize = 50): Promise<Paginated<StockMovement>> {
    return apiFetch<Paginated<StockMovement>>(
      `${BASE}/${id}/movements?page=${page}&page_size=${pageSize}`,
    );
  },

  /** POST /ingredients — alta (RF-P2-02). 201 creado · 422 inválido. */
  create(input: IngredientCreateInput): Promise<Ingredient> {
    return apiFetch<Ingredient>(BASE, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  /** PATCH /ingredients/{id} — actualización parcial (al menos un campo). */
  update(id: string, input: IngredientUpdateInput): Promise<Ingredient> {
    return apiFetch<Ingredient>(`${BASE}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  /** DELETE /ingredients/{id} — 204 si está libre · 409 si impacta recetas. */
  remove(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" });
  },

  /** POST /ingredients/{id}/stock — ajuste de stock (RF-P2-03). */
  adjustStock(id: string, input: StockAdjustInput): Promise<StockAdjustmentResponse> {
    return apiFetch<StockAdjustmentResponse>(`${BASE}/${id}/stock`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  /** POST /ingredients/import — importación por líneas (RF-P2-06). */
  importLines(lines: string[]): Promise<ImportResponse> {
    return apiFetch<ImportResponse>(`${BASE}/import`, {
      method: "POST",
      body: JSON.stringify({ lines }),
    });
  },
};

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

export const ingredientsService = {
  list(params: IngredientListParams = {}): Promise<Paginated<Ingredient>> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.status) query.set("status", params.status);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<Paginated<Ingredient>>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  getDetail(
    id: string,
    includeMovements = true,
  ): Promise<IngredientDetailResponse> {
    return apiFetch<IngredientDetailResponse>(
      `${BASE}/${id}?include_movements=${includeMovements ? "true" : "false"}`,
    );
  },

  listMovements(id: string, page = 1, pageSize = 50): Promise<Paginated<StockMovement>> {
    return apiFetch<Paginated<StockMovement>>(
      `${BASE}/${id}/movements?page=${page}&page_size=${pageSize}`,
    );
  },

  create(input: IngredientCreateInput): Promise<Ingredient> {
    return apiFetch<Ingredient>(BASE, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  update(id: string, input: IngredientUpdateInput): Promise<Ingredient> {
    return apiFetch<Ingredient>(`${BASE}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  remove(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" });
  },

  adjustStock(id: string, input: StockAdjustInput): Promise<StockAdjustmentResponse> {
    return apiFetch<StockAdjustmentResponse>(`${BASE}/${id}/stock`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  importLines(lines: string[]): Promise<ImportResponse> {
    return apiFetch<ImportResponse>(`${BASE}/import`, {
      method: "POST",
      body: JSON.stringify({ lines }),
    });
  },
};

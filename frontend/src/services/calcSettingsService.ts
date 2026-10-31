import { apiFetch } from "@/lib/api";
import type {
  CalcSettingsPayload,
  CalcSettingsResponse,
  Category,
  CategoryCreatePayload,
  CategoryKind,
  CategoryListResponse,
  CategoryUpdatePayload,
  DefaultCost,
  DefaultCostCreatePayload,
  DefaultCostListResponse,
  DefaultCostType,
  DefaultCostUpdatePayload,
  Supplier,
  SupplierCreatePayload,
  SupplierListResponse,
  SupplierUpdatePayload,
} from "@/types/calc";

// Parámetros de listado: ?q (1-120 chars), ?page, ?page_size (default 50, max 100).
// La búsqueda ?q es opcional: q vacío → lista completa (no se manda el parámetro).
export interface ListQuery {
  q?: string;
  page?: number;
  page_size?: number;
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function jsonOptions(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body) };
}

async function deleteViaApiFetch(endpoint: string): Promise<void> {
  await apiFetch<void>(endpoint, { method: "DELETE" });
}

export const calcSettingsService = {
  // ─── Settings (S1) ──────────────────────────────────────────────────────
  getSettings(): Promise<CalcSettingsResponse> {
    return apiFetch<CalcSettingsResponse>("/calc/settings");
  },

  updateSettings(payload: CalcSettingsPayload): Promise<CalcSettingsResponse> {
    return apiFetch<CalcSettingsResponse>(
      "/calc/settings",
      jsonOptions("PUT", payload)
    );
  },

  // ─── Categorías (material + product comparten shape) ───────────────────
  listCategories(
    kind: CategoryKind,
    query: ListQuery = {}
  ): Promise<CategoryListResponse> {
    return apiFetch<CategoryListResponse>(
      `/calc/${kind}${buildQuery({ ...query })}`
    );
  },

  createCategory(
    kind: CategoryKind,
    payload: CategoryCreatePayload
  ): Promise<Category> {
    return apiFetch<Category>(
      `/calc/${kind}`,
      jsonOptions("POST", payload)
    );
  },

  updateCategory(
    kind: CategoryKind,
    id: string,
    payload: CategoryUpdatePayload
  ): Promise<Category> {
    return apiFetch<Category>(
      `/calc/${kind}/${id}`,
      jsonOptions("PATCH", payload)
    );
  },

  deleteCategory(kind: CategoryKind, id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/${kind}/${id}`);
  },

  // ─── Suppliers ──────────────────────────────────────────────────────────
  listSuppliers(query: ListQuery = {}): Promise<SupplierListResponse> {
    return apiFetch<SupplierListResponse>(
      `/calc/suppliers${buildQuery({ ...query })}`
    );
  },

  createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
    return apiFetch<Supplier>(
      "/calc/suppliers",
      jsonOptions("POST", payload)
    );
  },

  updateSupplier(id: string, payload: SupplierUpdatePayload): Promise<Supplier> {
    return apiFetch<Supplier>(
      `/calc/suppliers/${id}`,
      jsonOptions("PATCH", payload)
    );
  },

  deleteSupplier(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/suppliers/${id}`);
  },

  // ─── Default costs ──────────────────────────────────────────────────────
  listDefaultCosts(
    query: ListQuery & { type?: DefaultCostType } = {}
  ): Promise<DefaultCostListResponse> {
    return apiFetch<DefaultCostListResponse>(
      `/calc/default-costs${buildQuery({ ...query })}`
    );
  },

  createDefaultCost(payload: DefaultCostCreatePayload): Promise<DefaultCost> {
    return apiFetch<DefaultCost>(
      "/calc/default-costs",
      jsonOptions("POST", payload)
    );
  },

  updateDefaultCost(
    id: string,
    payload: DefaultCostUpdatePayload
  ): Promise<DefaultCost> {
    return apiFetch<DefaultCost>(
      `/calc/default-costs/${id}`,
      jsonOptions("PATCH", payload)
    );
  },

  deleteDefaultCost(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/default-costs/${id}`);
  },
};

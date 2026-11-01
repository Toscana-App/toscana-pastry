import { apiFetch } from "@/lib/api";
import { pesosToCents } from "@/lib/format";
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

// Centavos (API) ↔ pesos (UI) para default_unit_cost_or_rate.
function defaultCostFromApi(cost: DefaultCost): DefaultCost {
  return {
    ...cost,
    default_unit_cost_or_rate: (
      Number(cost.default_unit_cost_or_rate) / 100
    ).toFixed(2),
  };
}

function defaultCostToApi<
  T extends { default_unit_cost_or_rate?: string },
>(payload: T): Omit<T, "default_unit_cost_or_rate"> & {
  default_unit_cost_or_rate?: number;
} {
  const { default_unit_cost_or_rate, ...rest } = payload;
  return default_unit_cost_or_rate === undefined
    ? rest
    : { ...rest, default_unit_cost_or_rate: pesosToCents(default_unit_cost_or_rate) };
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
  // La API habla centavos enteros en default_unit_cost_or_rate; la UI usa
  // pesos (string). Conversión solo en este borde.
  async listDefaultCosts(
    query: ListQuery & { type?: DefaultCostType } = {}
  ): Promise<DefaultCostListResponse> {
    const res = await apiFetch<DefaultCostListResponse>(
      `/calc/default-costs${buildQuery({ ...query })}`
    );
    return { ...res, items: res.items.map(defaultCostFromApi) };
  },

  async createDefaultCost(payload: DefaultCostCreatePayload): Promise<DefaultCost> {
    return defaultCostFromApi(
      await apiFetch<DefaultCost>(
        "/calc/default-costs",
        jsonOptions("POST", defaultCostToApi(payload))
      )
    );
  },

  async updateDefaultCost(
    id: string,
    payload: DefaultCostUpdatePayload
  ): Promise<DefaultCost> {
    return defaultCostFromApi(
      await apiFetch<DefaultCost>(
        `/calc/default-costs/${id}`,
        jsonOptions("PATCH", defaultCostToApi(payload))
      )
    );
  },

  deleteDefaultCost(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/default-costs/${id}`);
  },
};

import { apiFetch } from "@/lib/api";
import { pesosToCents } from "@/lib/format";
import type {
  ProductCreatePayload,
  ProductDetail,
  ProductListQuery,
  ProductListResponse,
  ProductUpdatePayload,
  ProductWithLines,
  ProductVersionListResponse,
  RecalculateAllResponse,
  PriceListResponse,
  DashboardResponse,
} from "@/types/calc";

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

function toApiPayload(payload: ProductCreatePayload | ProductUpdatePayload) {
  return {
    ...payload,
    labor: payload.labor?.map((line) => ({
      ...line,
      hourly_rate: pesosToCents(line.hourly_rate),
    })),
    extra_costs: payload.extra_costs?.map((line) => ({
      ...line,
      unit_cost: pesosToCents(line.unit_cost),
    })),
  };
}

async function deleteViaApiFetch(endpoint: string): Promise<void> {
  try {
    await apiFetch(endpoint, { method: "DELETE" });
  } catch (error) {
    if (error instanceof SyntaxError) return;
    throw error;
  }
}

export const calcProductsService = {
  listProducts(query: ProductListQuery = {}): Promise<ProductListResponse> {
    return apiFetch<ProductListResponse>(
      `/calc/products${buildQuery({ ...query })}`
    );
  },

  listPriceList(query: ProductListQuery = {}): Promise<PriceListResponse> {
    return apiFetch<PriceListResponse>(
      `/calc/products/price-list${buildQuery({ ...query })}`
    );
  },

  exportPriceList(query: ProductListQuery = {}): Promise<Response> {
    return apiFetch(
      `/calc/products/price-list/export${buildQuery({ ...query })}`
    );
  },

  getProduct(id: string): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(`/calc/products/${id}`);
  },

  createProduct(payload: ProductCreatePayload): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      "/calc/products",
      jsonOptions("POST", toApiPayload(payload))
    );
  },

  updateProduct(
    id: string,
    payload: ProductUpdatePayload
  ): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      `/calc/products/${id}`,
      jsonOptions("PATCH", toApiPayload(payload))
    );
  },

  deleteProduct(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/products/${id}`);
  },

  listProductVersions(
    id: string,
    query: { page?: number; page_size?: number } = {}
  ): Promise<ProductVersionListResponse> {
    return apiFetch<ProductVersionListResponse>(
      `/calc/products/${id}/versions${buildQuery({ ...query })}`
    );
  },

  recalculateProduct(id: string): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      `/calc/products/${id}/recalculate`,
      jsonOptions("POST", {})
    );
  },

  recalculateAllProducts(): Promise<RecalculateAllResponse> {
    return apiFetch<RecalculateAllResponse>(
      "/calc/products/recalculate-all",
      jsonOptions("POST", {})
    );
  },

  getDashboard(): Promise<DashboardResponse> {
    return apiFetch<DashboardResponse>("/calc/dashboard");
  },
};
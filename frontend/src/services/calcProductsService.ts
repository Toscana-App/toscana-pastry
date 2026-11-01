import { apiFetch } from "@/lib/api";
import type {
  ProductCreatePayload,
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

async function deleteViaApiFetch(endpoint: string): Promise<void> {
  try {
    await apiFetch(endpoint, { method: "DELETE" });
  } catch (error) {
    if (error instanceof SyntaxError) return;
    throw error;
  }
}

export const calcProductsService = {
  // GET /calc/products (RF-P3CC-01)
  listProducts(query: ProductListQuery = {}): Promise<ProductListResponse> {
    return apiFetch<ProductListResponse>(
      `/calc/products${buildQuery({ ...query })}`
    );
  },

  // GET /calc/products/price-list (RF-P3CC-04)
  listPriceList(query: ProductListQuery = {}): Promise<PriceListResponse> {
    return apiFetch<PriceListResponse>(
      `/calc/products/price-list${buildQuery({ ...query })}`
    );
  },

  // GET /calc/products/price-list/export (RF-P3CC-04)
  exportPriceList(query: ProductListQuery = {}): Promise<Response> {
    return apiFetch(
      `/calc/products/price-list/export${buildQuery({ ...query })}`
    );
  },

  // GET /calc/products/{id} (RF-P4CC-05)
  getProduct(id: string): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(`/calc/products/${id}`);
  },

  // POST /calc/products (RF-P4CC-01..05)
  createProduct(payload: ProductCreatePayload): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      "/calc/products",
      jsonOptions("POST", payload)
    );
  },

  // PATCH /calc/products/{id} (RF-P4CC-01/02)
  updateProduct(
    id: string,
    payload: ProductUpdatePayload
  ): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      `/calc/products/${id}`,
      jsonOptions("PATCH", payload)
    );
  },

  // DELETE /calc/products/{id}
  deleteProduct(id: string): Promise<void> {
    return deleteViaApiFetch(`/calc/products/${id}`);
  },

  // GET /calc/products/{id}/versions (RF-P4CC-07)
  listProductVersions(
    id: string,
    query: { page?: number; page_size?: number } = {}
  ): Promise<ProductVersionListResponse> {
    return apiFetch<ProductVersionListResponse>(
      `/calc/products/${id}/versions${buildQuery({ ...query })}`
    );
  },

  // POST /calc/products/{id}/recalculate (RF-P4CC-06)
  recalculateProduct(id: string): Promise<ProductWithLines> {
    return apiFetch<ProductWithLines>(
      `/calc/products/${id}/recalculate`,
      jsonOptions("POST", {})
    );
  },

  // POST /calc/products/recalculate-all (RF-P3CC-03)
  recalculateAllProducts(): Promise<RecalculateAllResponse> {
    return apiFetch<RecalculateAllResponse>(
      "/calc/products/recalculate-all",
      jsonOptions("POST", {})
    );
  },

  // GET /calc/dashboard (RF-P3CC-05)
  getDashboard(): Promise<DashboardResponse> {
    return apiFetch<DashboardResponse>("/calc/dashboard");
  },
};
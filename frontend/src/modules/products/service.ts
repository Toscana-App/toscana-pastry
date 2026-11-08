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

export const productsService = {
  list(params: ProductListParams = {}): Promise<ProductListResponse> {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.category) query.set("category", params.category);
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    return apiFetch<ProductListResponse>(`${BASE}${qs ? `?${qs}` : ""}`);
  },

  getDetail(id: string): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(`${BASE}/${id}`);
  },

  create(input: ProductCreateInput): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(BASE, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  update(id: string, input: ProductUpdateInput): Promise<ProductDetail> {
    return apiFetch<ProductDetail>(`${BASE}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
  },

  remove(id: string): Promise<ProductDeleteImpact | null> {
    return apiFetch<ProductDeleteImpact | void>(`${BASE}/${id}`, {
      method: "DELETE",
    }).then((body) => (body ?? null) as ProductDeleteImpact | null);
  },

  uploadImage(id: string, file: File): Promise<ProductImageResponse> {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<ProductImageResponse>(`${BASE}/${id}/image`, {
      method: "POST",
      body: form,
    });
  },

  removeImage(id: string): Promise<void> {
    return apiFetch<void>(`${BASE}/${id}/image`, { method: "DELETE" });
  },

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

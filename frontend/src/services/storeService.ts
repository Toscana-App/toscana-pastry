import { apiFetch } from "@/lib/api";
import type { Audience, Product, StoreProductDetail } from "@/types/pricing";

export interface StoreListResponse {
  audience: Audience;
  products: Product[];
  total: number;
  categories: string[];
}

export function fetchStoreList(
  audience: Audience,
  q?: string,
): Promise<StoreListResponse> {
  const params = new URLSearchParams();
  params.set("audience", audience);
  if (q) params.set("q", q);
  return apiFetch<StoreListResponse>(`/products?${params.toString()}`);
}

export function fetchStoreDetail(
  id: string,
  audience: Audience,
): Promise<StoreProductDetail> {
  return apiFetch<StoreProductDetail>(`/products/${id}?audience=${audience}`);
}

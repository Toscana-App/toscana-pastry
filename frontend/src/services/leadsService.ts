/** Services de leads (C5, RF-P11-13) y coupons (admin ABM, F4).

Cupones: `value` viaja como string (Money, RNF-P4-02).
*/

import { apiFetch } from "@/lib/api";
import {
  CouponCreatePayload,
  CouponListResponse,
  CouponOut,
  CouponStatus,
  LeadCreatePayload,
  LeadListResponse,
  LeadOut,
} from "@/types/leads";

// ─── Leads ─────────────────────────────────────────────────────────

/** POST /leads — captura pública de contacto (202, sin auth). */
export async function createLead(
  payload: LeadCreatePayload
): Promise<{ id: string }> {
  return apiFetch("/leads", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET /leads — listado admin (query: q, read, customer_type, page). */
export async function fetchLeads(params: {
  q?: string;
  read?: boolean;
  customer_type?: string;
  page?: number;
  page_size?: number;
}): Promise<LeadListResponse> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.read !== undefined) {
    search.set("read", String(params.read));
  }
  if (params.customer_type) {
    search.set("customer_type", params.customer_type);
  }
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiFetch(`/leads${qs ? `?${qs}` : ""}`);
}

/** PATCH /leads/{id}/read — marca leído/no leído. */
export async function setLeadRead(
  leadId: string,
  read: boolean
): Promise<LeadOut> {
  return apiFetch(`/leads/${leadId}/read`, {
    method: "PATCH",
    body: JSON.stringify({ read }),
  });
}

/** POST /leads/read-all — marca todos como leídos. */
export async function markAllLeadsRead(): Promise<{ updated: number }> {
  return apiFetch("/leads/read-all", { method: "POST" });
}

// ─── Coupons ───────────────────────────────────────────────────────

/** GET /coupons — listado admin. */
export async function fetchCoupons(
  page = 1,
  pageSize = 50
): Promise<CouponListResponse> {
  return apiFetch(`/coupons?page=${page}&page_size=${pageSize}`);
}

/** POST /coupons — crea (409 si el código ya existe). */
export async function createCoupon(
  payload: CouponCreatePayload
): Promise<CouponOut> {
  const res = await apiFetch<{ coupon: CouponOut }>("/coupons", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return res.coupon;
}

/** PATCH /coupons/{id} — edita (incluye toggle active/paused). */
export async function updateCoupon(
  couponId: string,
  data: Partial<CouponCreatePayload>
): Promise<CouponOut> {
  const res = await apiFetch<{ coupon: CouponOut }>(
    `/coupons/${couponId}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    }
  );
  return res.coupon;
}

/** PATCH /coupons/{id} — cambia solo el estado (active/paused). */
export async function setCouponStatus(
  couponId: string,
  status: CouponStatus
): Promise<CouponOut> {
  return updateCoupon(couponId, { status });
}

/** DELETE /coupons/{id} — elimina (204). */
export async function deleteCoupon(couponId: string): Promise<void> {
  await apiFetch(`/coupons/${couponId}`, { method: "DELETE" });
}

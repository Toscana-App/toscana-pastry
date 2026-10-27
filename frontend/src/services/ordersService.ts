/** Portal order-flow services (C4 cart, C2 addresses, C6 orders). */

import { apiFetch } from "@/lib/api";
import {
  AddressEnvelope,
  AddressListResponse,
  OrderDetail,
  PortalOrderPayload,
} from "@/types/orders";

/**
 * POST /orders/{id}/payment: starts the online payment (RF-P11-10).
 * The order owner (or an admin) may call it; idempotent by key.
 */
export async function initOrderPayment(
  orderId: string,
  idempotencyKey: string
): Promise<{ reference: string; checkout_url: string }> {
  return apiFetch("/orders" + `/${orderId}/payment`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

/** GET /orders/{id}/payment: payment status (polling ≤ 5 s, F3). */
export async function fetchOrderPaymentStatus(
  orderId: string
): Promise<{
  status: string | null;
  paid: boolean;
  payment_reference: string | null;
  updated_at: string | null;
}> {
  return apiFetch(`/orders/${orderId}/payment`);
}

/**
 * POST /orders — creation from the portal (C6).
 * Returns the created order (with its `code`, TPxxxxxx).
 * 409 with detail "order_window_closed" when the order window is closed.
 */
export async function createPortalOrder(
  payload: PortalOrderPayload
): Promise<OrderDetail> {
  return apiFetch<OrderDetail>("/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET /orders/mine — paginated list of the user's orders (RF-P11-08). */
export async function fetchMyOrders(
  page = 1,
  pageSize = 20
): Promise<{
  orders: OrderDetail[];
  total: number;
  page: number;
  page_size: number;
}> {
  return apiFetch(`/orders/mine?page=${page}&page_size=${pageSize}`);
}

/** GET /orders/mine/{code} — detail by code (anti-spoofing: 404 for others'). */
export async function fetchMyOrderByCode(code: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/mine/${code}`);
}

/** GET /customers/me/addresses — address book (C2). */
export async function fetchMyAddresses(): Promise<AddressListResponse> {
  return apiFetch<AddressListResponse>("/customers/me/addresses");
}

/** POST /customers/me/addresses — new address (stored in the book). */
export async function createMyAddress(data: {
  street_line_1: string;
  street_line_2?: string | null;
  city?: string | null;
  postal_code?: string | null;
  province?: string | null;
  phone?: string | null;
}): Promise<AddressEnvelope> {
  return apiFetch<AddressEnvelope>("/customers/me/addresses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** PATCH /customers/me/addresses/{id} — edits one (is_default=true undoes the other). */
export async function updateMyAddress(
  addressId: string,
  data: {
    street_line_1?: string;
    street_line_2?: string | null;
    city?: string | null;
    postal_code?: string | null;
    province?: string | null;
    phone?: string | null;
    is_default?: boolean;
  }
): Promise<AddressEnvelope> {
  return apiFetch<AddressEnvelope>(`/customers/me/addresses/${addressId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** DELETE /customers/me/addresses/{id} — 409 if it is the only one; 404 if it belongs to someone else. */
export async function deleteMyAddress(addressId: string): Promise<void> {
  await apiFetch(`/customers/me/addresses/${addressId}`, {
    method: "DELETE",
  });
}

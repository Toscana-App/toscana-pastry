/** Services del flujo de pedido del portal (C4 cart, C2 addresses, C6 orders). */

import { apiFetch } from "@/lib/api";
import {
  AddressEnvelope,
  AddressListResponse,
  OrderDetail,
  PortalOrderPayload,
} from "@/types/orders";

/**
 * POST /orders/{id}/payment: inicia el pago online (RF-P11-10).
 * El propietario del pedido (o admin) puede invocar; idempotente por clave.
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

/** GET /orders/{id}/payment: estado del pago (polling ≤ 5 s, F3). */
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
 * POST /orders — creación desde el portal (C6).
 * Devuelve el pedido creado (con `code` TPxxxxxx).
 * 409 con detail "order_window_closed" si la ventana de pedidos está cerrada.
 */
export async function createPortalOrder(
  payload: PortalOrderPayload
): Promise<OrderDetail> {
  return apiFetch<OrderDetail>("/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** GET /customers/me/addresses — libro de direcciones (C2). */
export async function fetchMyAddresses(): Promise<AddressListResponse> {
  return apiFetch<AddressListResponse>("/customers/me/addresses");
}

/** POST /customers/me/addresses — nueva dirección (se guarda en el libro). */
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

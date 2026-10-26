/** Services del flujo de pedido del portal (C4 cart, C2 addresses, C6 orders). */

import { apiFetch } from "@/lib/api";
import {
  AddressEnvelope,
  AddressListResponse,
  CartResponse,
  OrderDetail,
  PortalOrderPayload,
} from "@/types/orders";

/** GET /cart — carrito server-side con precio derivado de la audiencia (C4). */
export async function fetchCart(): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart");
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

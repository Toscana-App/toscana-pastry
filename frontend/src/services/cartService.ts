/** Server-side cart service (C4, RF-P11-03/14).

Amounts travel as strings (Money, RNF-P4-02).
*/

import { apiFetch } from "@/lib/api";
import { CartResponse } from "@/types/orders";

/** Evento global: el carrito cambió (lo escucha el badge de la navbar). */
export const CART_CHANGED_EVENT = "cart:changed";

function announceCartChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CART_CHANGED_EVENT));
  }
}

/** GET /cart */
export async function fetchCart(): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart");
}

/**
 * POST /cart/items: adds or changes a line's quantity (upsert).
 * 404 if the product does not exist; 422 when the 50-line limit is exceeded.
 */
export async function addCartItem(
  product_id: string,
  qty: number
): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>("/cart/items", {
    method: "POST",
    body: JSON.stringify({ product_id, qty }),
  });
  announceCartChanged();
  return cart;
}

/** DELETE /cart/items/{product_id} */
export async function removeCartItem(
  product_id: string
): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>(`/cart/items/${product_id}`, {
    method: "DELETE",
  });
  announceCartChanged();
  return cart;
}

/**
 * POST /cart/coupon: applies a coupon.
 * 422 with a descriptive detail when the coupon is invalid for the audience.
 */
export async function applyCoupon(code: string): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>("/cart/coupon", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  announceCartChanged();
  return cart;
}

/** DELETE /cart/coupon */
export async function removeCoupon(): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>("/cart/coupon", {
    method: "DELETE",
  });
  announceCartChanged();
  return cart;
}

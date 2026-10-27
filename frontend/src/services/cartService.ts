/** Server-side cart service (C4, RF-P11-03/14).

Amounts travel as strings (Money, RNF-P4-02).
*/

import { apiFetch } from "@/lib/api";
import { CartResponse } from "@/types/orders";

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
  return apiFetch<CartResponse>("/cart/items", {
    method: "POST",
    body: JSON.stringify({ product_id, qty }),
  });
}

/** DELETE /cart/items/{product_id} */
export async function removeCartItem(
  product_id: string
): Promise<CartResponse> {
  return apiFetch<CartResponse>(`/cart/items/${product_id}`, {
    method: "DELETE",
  });
}

/**
 * POST /cart/coupon: applies a coupon.
 * 422 with a descriptive detail when the coupon is invalid for the audience.
 */
export async function applyCoupon(code: string): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart/coupon", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

/** DELETE /cart/coupon */
export async function removeCoupon(): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart/coupon", {
    method: "DELETE",
  });
}

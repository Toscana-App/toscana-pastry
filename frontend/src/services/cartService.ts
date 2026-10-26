/** Service del carrito server-side (C4, RF-P11-03/14).

Los montos viajan como string (Money, RNF-P4-02).
*/

import { apiFetch } from "@/lib/api";
import { CartResponse } from "@/types/orders";

/** GET /cart */
export async function fetchCart(): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart");
}

/**
 * POST /cart/items: agrega o altera la cantidad de una línea (upsert).
 * 404 si el producto no existe; 422 si se superan las 50 líneas.
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
 * POST /cart/coupon: aplica un cupón.
 * 422 con detail descriptivo si el cupón no es válido para la audiencia.
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

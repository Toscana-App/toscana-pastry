
import { apiFetch } from "@/lib/api";
import { CartResponse } from "@/types/orders";

export const CART_CHANGED_EVENT = "cart:changed";

function announceCartChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CART_CHANGED_EVENT));
  }
}

export async function fetchCart(): Promise<CartResponse> {
  return apiFetch<CartResponse>("/cart");
}

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

export async function removeCartItem(
  product_id: string
): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>(`/cart/items/${product_id}`, {
    method: "DELETE",
  });
  announceCartChanged();
  return cart;
}

export async function applyCoupon(code: string): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>("/cart/coupon", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  announceCartChanged();
  return cart;
}

export async function removeCoupon(): Promise<CartResponse> {
  const cart = await apiFetch<CartResponse>("/cart/coupon", {
    method: "DELETE",
  });
  announceCartChanged();
  return cart;
}

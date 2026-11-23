import { describe, expect, it } from "vitest";
import { cartItems, cartValue, catalogItems } from "./ga4-ecommerce";
import type { CartItemOut, CartResponse } from "@/types/orders";
import type { Product } from "@/types/pricing";

function product(overrides: Partial<Product> = {}): Product {
  return {
    id: "p1",
    name: "Torta de chocolate",
    category: "Tortas",
    description: "",
    image_url: null,
    price: "17500",
    price_per_serving: null,
    complete: true,
    tags: [],
    ...overrides,
  };
}

function cart(items: CartItemOut[], total: string): CartResponse {
  return {
    audience: "consumidor_final",
    items,
    subtotal: total,
    total,
    discount_amount: "0",
    coupon: null,
  };
}

describe("ga4-ecommerce (helpers)", () => {
  it("catalogItems convierte el precio string a número con currency ARS", () => {
    expect(catalogItems([product()])).toEqual([
      {
        item_id: "p1",
        item_name: "Torta de chocolate",
        price: 17500,
        quantity: 1,
        currency: "ARS",
      },
    ]);
  });

  it("catalogItems devuelve lista vacía con catálogo vacío", () => {
    expect(catalogItems([])).toEqual([]);
  });

  it("catalogItems omite productos sin precio válido", () => {
    expect(
      catalogItems([product({ price: "" }), product({ price: "abc" })]),
    ).toEqual([]);
  });

  it("cartItems mapea el carrito al shape GA4 (string a número, qty, ARS)", () => {
    expect(
      cartItems(
        cart(
          [
            {
              product_id: "p1",
              name: "Torta de chocolate",
              unit_price: "17500",
              qty: 1,
              total: "17500",
            },
            {
              product_id: "p2",
              name: "Cheesecake",
              unit_price: "12000.50",
              qty: 2,
              total: "24001",
            },
          ],
          "41501.50",
        ),
      ),
    ).toEqual([
      {
        item_id: "p1",
        item_name: "Torta de chocolate",
        price: 17500,
        quantity: 1,
        currency: "ARS",
      },
      {
        item_id: "p2",
        item_name: "Cheesecake",
        price: 12000.5,
        quantity: 2,
        currency: "ARS",
      },
    ]);
  });

  it("cartItems devuelve lista vacía con carrito vacío", () => {
    expect(cartItems(cart([], "0"))).toEqual([]);
  });

  it("cartValue convierte el total string a número", () => {
    expect(cartValue(cart([], "41501.5"))).toBe(41501.5);
  });
});

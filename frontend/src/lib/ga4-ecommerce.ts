import type { Product } from "@/types/pricing";
import type { CartResponse } from "@/types/orders";

export type Ga4Item = {
  item_id: string;
  item_name: string;
  price: number;
  quantity: number;
  currency: "ARS";
};

export function catalogItems(products: Product[]): Ga4Item[] {
  const items: Ga4Item[] = [];
  for (const product of products) {
    if (!product.price) continue;
    const price = Number(product.price);
    if (!Number.isFinite(price)) continue;
    items.push({
      item_id: product.id,
      item_name: product.name,
      price,
      quantity: 1,
      currency: "ARS",
    });
  }
  return items;
}

export function cartItems(cart: CartResponse): Ga4Item[] {
  return cart.items.map((item) => ({
    item_id: item.product_id,
    item_name: item.name,
    price: Number(item.unit_price),
    quantity: item.qty,
    currency: "ARS",
  }));
}

export function cartValue(cart: CartResponse): number {
  return Number(cart.total);
}

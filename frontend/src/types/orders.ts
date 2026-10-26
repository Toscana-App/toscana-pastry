/** Tipos del flujo de pedidos/carrito del portal (p11 F2/F3, backend C4/C6).

Los montos viajan como string (Money, RNF-P4-02): nunca float en la API.
*/

export type DeliveryMode = "delivery" | "pickup";

export type PaymentMethod = "mercadopago" | "cash";

export interface CartItemOut {
  product_id: string;
  name: string;
  unit_price: string;
  qty: number;
  total: string;
}

export interface CartCouponOut {
  code: string;
  type: string;
  value: string;
}

export interface CartResponse {
  audience: string;
  items: CartItemOut[];
  subtotal: string;
  total: string;
  discount_amount: string;
  coupon: CartCouponOut | null;
}

export interface Address {
  id: string;
  street_line_1: string;
  street_line_2: string | null;
  city: string | null;
  postal_code: string | null;
  province: string | null;
  phone: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface AddressListResponse {
  items: Address[];
}

export interface AddressEnvelope {
  address: Address;
}

/** Línea de pedido en la respuesta del backend (snapshot). */
export interface OrderItemOut {
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: string;
  portion_note: string;
  total: string;
}

export interface OrderDetail {
  id: string;
  code: string;
  customer_id: string;
  status: string;
  date: string;
  payment_method: PaymentMethod;
  delivery_mode: DeliveryMode;
  delivery_address: string | null;
  coupon_code: string | null;
  discount_amount: string | null;
  paid: boolean;
  payment_status: string | null;
  total: string;
  items: OrderItemOut[];
  created_at: string;
}

/** Payload de POST /orders (portal creation, C6 — PortalOrderCreateRequest). */
export interface PortalOrderPayload {
  items: {
    product_id: string;
    product_name: string;
    quantity: number;
    unit_price: string;
    portion_note: string;
  }[];
  date: string;
  delivery_mode: DeliveryMode;
  delivery_address: string | null;
  payment_method: PaymentMethod;
  coupon_code: string | null;
}

/** Formatea un address (libro) como la string plana que espera POST /orders. */
export function addressToLine(a: Address): string {
  const parts = [
    a.street_line_1,
    a.street_line_2,
    a.city,
    a.postal_code ? `CP ${a.postal_code}` : null,
    a.province,
  ].filter(Boolean);
  return parts.join(", ");
}

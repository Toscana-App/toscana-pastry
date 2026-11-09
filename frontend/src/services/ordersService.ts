
import { apiFetch } from "@/lib/api";
import {
  AddressEnvelope,
  AddressListResponse,
  OrderDetail,
  PortalOrderPayload,
} from "@/types/orders";

export async function initOrderPayment(
  orderId: string,
  idempotencyKey: string
): Promise<{ reference: string; checkout_url: string }> {
  return apiFetch("/orders" + `/${orderId}/payment`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

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

export async function createPortalOrder(
  payload: PortalOrderPayload
): Promise<OrderDetail> {
  return apiFetch<OrderDetail>("/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

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

export async function fetchMyOrderByCode(code: string): Promise<OrderDetail> {
  return apiFetch<OrderDetail>(`/orders/mine/${code}`);
}

export async function fetchMyAddresses(): Promise<AddressListResponse> {
  return apiFetch<AddressListResponse>("/customers/me/addresses");
}

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

export async function deleteMyAddress(addressId: string): Promise<void> {
  await apiFetch(`/customers/me/addresses/${addressId}`, {
    method: "DELETE",
  });
}

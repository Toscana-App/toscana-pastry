export type DeliveryLinkState = "active" | "delivered" | "cancelled" | "expired";

export interface DeliveryLink {
  token: string;
  url: string;
  state: DeliveryLinkState;
  created_at: string | null;
}

export interface PublicDelivery {
  state: DeliveryLinkState;
  order_code: string;
  status: string;
  status_label: string;
  message: string;
}

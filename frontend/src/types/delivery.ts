export type DeliveryLinkState = "active" | "delivered" | "cancelled" | "expired";

export interface DeliveryLink {
  token: string;
  url: string;
  state: DeliveryLinkState;
  created_at: string | null;
}

export interface PublicDeliveryItem {
  name: string;
  quantity: number;
}

export interface PublicDelivery {
  state: DeliveryLinkState;
  order_code: string;
  status: string;
  status_label: string;
  message: string;
  items?: PublicDeliveryItem[];
}

/** Per-step data for the 5-step checkout (F2 — p11 UC-04…08). */

import { DeliveryMode, PaymentMethod } from "@/types/orders";

/** Step 1 — Contact (RF-P11-04, E.164 +54 default). */
export interface ContactData {
  name: string;
  phone: string; // E.164
  email: string;
}

/** Step 2 — Selected address (RF-P11-05). */
export interface AddressSelection {
  addressId: string | null; // null = new address created on confirm
  line: string; // flat string for POST /orders (delivery_address)
}

/** Step 3 — Delivery (RF-P11-06). */
export interface DeliveryData {
  date: string; // YYYY-MM-DD, ≥ today + min_lead_days
  delivery_mode: DeliveryMode;
}

/** Step 4 — Payment (RF-P11-07). */
export interface PaymentData {
  payment_method: PaymentMethod;
}

/** Stepper step titles (order matters). */
export const STEP_TITLES = [
  "Contacto",
  "Dirección",
  "Entrega",
  "Pago",
  "Confirmar",
] as const;

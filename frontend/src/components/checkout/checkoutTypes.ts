/** Datos por paso del checkout de 5 pasos (F2 — p11 UC-04…08). */

import { DeliveryMode, PaymentMethod } from "@/types/orders";

/** Paso 1 — Contacto (RF-P11-04, E.164 +54 default). */
export interface ContactData {
  name: string;
  phone: string; // E.164
  email: string;
}

/** Paso 2 — Dirección elegida (RF-P11-05). */
export interface AddressSelection {
  addressId: string | null; // null = dirección nueva creada al confirmar
  line: string; // string plana para POST /orders (delivery_address)
}

/** Paso 3 — Entrega (RF-P11-06). */
export interface DeliveryData {
  date: string; // YYYY-MM-DD, ≥ hoy + min_lead_days
  delivery_mode: DeliveryMode;
}

/** Paso 4 — Pago (RF-P11-07). */
export interface PaymentData {
  payment_method: PaymentMethod;
}

/** Títulos de los pasos del stepper (orden importa). */
export const STEP_TITLES = [
  "Contacto",
  "Dirección",
  "Entrega",
  "Pago",
  "Confirmar",
] as const;

"use client";

import { CheckoutFlow } from "@/components/checkout/CheckoutFlow";

/**
 * /checkout — 5 pasos (F2 — p11 RF-P11-02…08):
 * Contacto → Dirección → Entrega → Pago → Revisar y confirmar.
 * El pedido se crea solo en el paso 5 (C6).
 */
export default function CheckoutPage() {
  return <CheckoutFlow />;
}

"use client";

import { CheckoutFlow } from "@/components/checkout/CheckoutFlow";

/**
 * /checkout — 5 steps (F2 — p11 RF-P11-02…08):
 * Contact → Address → Delivery → Payment → Review & confirm.
 * The order is created only on step 5 (C6).
 */
export default function CheckoutPage() {
  return <CheckoutFlow />;
}

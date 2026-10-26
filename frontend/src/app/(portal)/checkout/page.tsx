"use client";

import { ComingSoon } from "@/components/portal/ComingSoon";

/**
 * CTA "Nuevo pedido" → checkout de 5 pasos (F2, p11 RF-P11-02…08):
 * Contacto → Dirección → Entrega → Pago → Revisar y confirmar.
 */
export default function CheckoutPage() {
  return (
    <ComingSoon
      title="Nuevo pedido"
      message="El checkout de 5 pasos (contacto, dirección, entrega, pago y confirmación) estará disponible próximamente."
    />
  );
}

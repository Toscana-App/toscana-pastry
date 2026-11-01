import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { OrderWizard } from "@/modules/orders/components/OrderWizard";

export const metadata: Metadata = {
  title: "Nuevo pedido",
};

/** Las mutaciones de pedidos son de administración (RBAC). */
export default function NewOrderRoute() {
  return (
    <ProtectedRoute requiredRole="admin">
      <OrderWizard />
    </ProtectedRoute>
  );
}

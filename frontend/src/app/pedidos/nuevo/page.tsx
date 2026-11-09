import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { OrderWizard } from "@/modules/orders/components/OrderWizard";

export const metadata: Metadata = {
  title: "Nuevo pedido",
};

export default function NewOrderRoute() {
  return (
    <ProtectedRoute requiredRole="admin">
      <OrderWizard />
    </ProtectedRoute>
  );
}

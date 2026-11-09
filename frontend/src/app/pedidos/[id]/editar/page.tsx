import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { OrderWizard } from "@/modules/orders/components/OrderWizard";

export const metadata: Metadata = {
  title: "Editar pedido",
};

export default async function EditOrderRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <ProtectedRoute requiredRole="admin">
      <OrderWizard orderId={id} />
    </ProtectedRoute>
  );
}

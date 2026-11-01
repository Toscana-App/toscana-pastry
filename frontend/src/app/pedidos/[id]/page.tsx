import type { Metadata } from "next";
import { OrderDetailPage } from "@/modules/orders/components/OrderDetailPage";

export const metadata: Metadata = {
  title: "Detalle de pedido",
};

/**
 * Next 16: `params` es una Promise en server components; se resuelve acá y
 * el id (string) entra al componente cliente.
 */
export default async function OrderDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OrderDetailPage orderId={id} />;
}

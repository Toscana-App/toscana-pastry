import type { Metadata } from "next";
import { DeliveryStatusView } from "@/modules/delivery/delivery_status_view";

export const instant = false;

export const metadata: Metadata = {
  title: "Estado de tu pedido · Pastelería Toscana",
  description:
    "Estado de tu pedido de Pastelería Toscana. Escaneado desde el QR de entrega.",
};

export default async function DeliveryStatusPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <DeliveryStatusView token={token} />;
}

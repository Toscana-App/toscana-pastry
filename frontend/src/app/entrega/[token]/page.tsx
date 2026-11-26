import { DeliveryStatusView } from "@/modules/delivery/delivery_status_view";

export const instant = false;

export default async function DeliveryStatusPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <DeliveryStatusView token={token} />;
}

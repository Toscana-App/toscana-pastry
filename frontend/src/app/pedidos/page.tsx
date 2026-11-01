import type { Metadata } from "next";
import { OrdersPage } from "@/modules/orders/components/OrdersPage";

export const metadata: Metadata = {
  title: "Pedidos",
  description: "Listado de pedidos con filtros por estado, cliente y fecha.",
};

export default function OrdersRoute() {
  return <OrdersPage />;
}

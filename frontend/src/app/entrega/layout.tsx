import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Entrega de pedido | Toscana Pastry",
  robots: { index: false, follow: false },
};

export default function DeliveryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}

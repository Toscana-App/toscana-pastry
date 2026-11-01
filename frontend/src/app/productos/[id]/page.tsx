import type { Metadata } from "next";
import { ProductDetailPage } from "@/modules/products/components/ProductDetailPage";

export const metadata: Metadata = {
  title: "Detalle de producto",
};

/**
 * Next 16: `params` es una Promise en server components; se resuelve acá y
 * el id (string) entra al componente cliente.
 */
export default async function ProductDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProductDetailPage productId={id} />;
}

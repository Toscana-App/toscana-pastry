import type { Metadata } from "next";
import { ProductDetailPage } from "@/modules/products/components/ProductDetailPage";

export const metadata: Metadata = {
  title: "Detalle de producto",
};

export default async function ProductDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProductDetailPage productId={id} />;
}

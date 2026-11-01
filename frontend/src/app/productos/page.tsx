import type { Metadata } from "next";
import { ProductsPage } from "@/modules/products/components/ProductsPage";

export const metadata: Metadata = {
  title: "Productos",
  description: "Catálogo de productos con precios calculados por receta.",
};

export default function ProductsRoute() {
  return <ProductsPage />;
}

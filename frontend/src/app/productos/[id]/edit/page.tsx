import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ProductFormPage } from "@/modules/products/components/ProductFormPage";

export const metadata: Metadata = {
  title: "Editar producto",
};

export default async function EditProductRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <ProtectedRoute requiredRole="admin">
      <ProductFormPage mode="edit" productId={id} />
    </ProtectedRoute>
  );
}

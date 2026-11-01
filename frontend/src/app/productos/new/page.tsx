import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ProductFormPage } from "@/modules/products/components/ProductFormPage";

export const metadata: Metadata = {
  title: "Nuevo producto",
};

/** Las mutaciones de productos son de administración (RBAC). */
export default function NewProductRoute() {
  return (
    <ProtectedRoute requiredRole="admin">
      <ProductFormPage mode="create" />
    </ProtectedRoute>
  );
}

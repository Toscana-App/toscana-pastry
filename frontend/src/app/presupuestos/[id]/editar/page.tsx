import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { BudgetEditPage } from "@/modules/budgets/components/BudgetEditPage";

export const metadata: Metadata = {
  title: "Editar presupuesto",
};

/** Las mutaciones de presupuestos son de administración (RBAC). */
export default async function EditBudgetRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <ProtectedRoute requiredRole="admin">
      <BudgetEditPage budgetId={id} />
    </ProtectedRoute>
  );
}

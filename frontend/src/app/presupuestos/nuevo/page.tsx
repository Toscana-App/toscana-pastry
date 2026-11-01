import type { Metadata } from "next";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { BudgetWizard } from "@/modules/budgets/components/BudgetWizard";

export const metadata: Metadata = {
  title: "Nuevo presupuesto",
};

/** Las mutaciones de presupuestos son de administración (RBAC). */
export default function NewBudgetRoute() {
  return (
    <ProtectedRoute requiredRole="admin">
      <BudgetWizard />
    </ProtectedRoute>
  );
}

import type { Metadata } from "next";
import { BudgetDetailPage } from "@/modules/budgets/components/BudgetDetailPage";

export const metadata: Metadata = {
  title: "Detalle de presupuesto",
};

/**
 * Next 16: `params` es una Promise en server components; se resuelve acá y
 * el id (string) entra al componente cliente.
 */
export default async function BudgetDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BudgetDetailPage budgetId={id} />;
}

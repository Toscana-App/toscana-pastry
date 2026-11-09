import type { Metadata } from "next";
import { BudgetDetailPage } from "@/modules/budgets/components/BudgetDetailPage";

export const metadata: Metadata = {
  title: "Detalle de presupuesto",
};

export default async function BudgetDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BudgetDetailPage budgetId={id} />;
}

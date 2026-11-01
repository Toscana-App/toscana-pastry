import type { Metadata } from "next";
import { BudgetsPage } from "@/modules/budgets/components/BudgetsPage";

export const metadata: Metadata = {
  title: "Presupuestos",
  description: "Listado de presupuestos con filtros por estado y fecha.",
};

export default function BudgetsRoute() {
  return <BudgetsPage />;
}

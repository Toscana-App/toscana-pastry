import type { Metadata } from "next";
import { IngredientsPage } from "@/modules/ingredients/components/IngredientsPage";

export const metadata: Metadata = {
  title: "Ingredientes",
  description: "Alta, edición y control de stock de ingredientes.",
};

export default function AdminIngredientsRoute() {
  return <IngredientsPage />;
}

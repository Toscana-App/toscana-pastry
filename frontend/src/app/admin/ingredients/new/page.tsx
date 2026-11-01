import type { Metadata } from "next";
import { IngredientFormPage } from "@/modules/ingredients/components/IngredientFormPage";

export const metadata: Metadata = {
  title: "Nuevo ingrediente",
};

export default function NewIngredientRoute() {
  return <IngredientFormPage mode="create" />;
}

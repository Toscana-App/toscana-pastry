import type { Metadata } from "next";
import { IngredientFormPage } from "@/modules/ingredients/components/IngredientFormPage";

export const metadata: Metadata = {
  title: "Editar ingrediente",
};

export default async function EditIngredientRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <IngredientFormPage mode="edit" ingredientId={id} />;
}

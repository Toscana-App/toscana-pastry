import type { Metadata } from "next";
import { IngredientDetailPage } from "@/modules/ingredients/components/IngredientDetailPage";

export const metadata: Metadata = {
  title: "Detalle del ingrediente",
};

/**
 * Ruta dinámica: en Next 15+ `params` es una Promise. Se resuelve en el
 * servidor y se le pasa el id (string) al componente cliente.
 */
export default async function IngredientDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <IngredientDetailPage id={id} />;
}

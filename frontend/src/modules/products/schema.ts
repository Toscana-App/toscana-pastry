import { z } from "zod";
import { PRODUCT_DIFFICULTIES, RECIPE_UNITS } from "./types";

/**
 * Esquemas zod del módulo de productos (Fase 5, RF-P4-06: validación por
 * campo, errores inline).
 *
 * El client es la PRIMERA línea de validación; el backend sigue siendo la
 * última (422 si algo se cuela). `.strict()` porque el backend usa
 * `extra="forbid"`: un typo muere acá, no en el payload.
 *
 * El formulario (crear/editar) usa `productFormSchema` con los tres campos de
 * preparación SIEMPRE presentes: así el Costos (preview en vivo) siempre tiene
 * datos, y en editar el backend los recibe como campos definidos.
 */

/** Línea de receta (RF-P4-02): insumo + cantidad > 0 + unidad del contrato. */
export const recipeItemSchema = z
  .object({
    ingredient_id: z
      .string()
      .trim()
      .min(1, "Elegí un insumo")
      .max(36, "Insumo inválido"),
    qty: z
      .number({ message: "Ingresá una cantidad" })
      .positive("Debe ser mayor que 0"),
    unit: z.enum(RECIPE_UNITS, { message: "Unidad inválida" }),
  })
  .strict();

export type RecipeItemValues = z.infer<typeof recipeItemSchema>;

export const productFormSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(2, "Mínimo 2 caracteres")
      .max(120, "Máximo 120 caracteres"),
    category: z
      .string()
      .trim()
      .min(1, "Ingresá una categoría")
      .max(60, "Máximo 60 caracteres"),
    description: z
      .string()
      .trim()
      .max(500, "Máximo 500 caracteres")
      .optional(),
    prep_time_min: z
      .number({ message: "Ingresá un tiempo válido" })
      .int("Debe ser entero")
      .min(1, "Debe ser mayor que 0")
      .max(1440, "Máximo 1440 minutos"),
    servings: z
      .number({ message: "Ingresá una cantidad válida" })
      .int("Debe ser entero")
      .min(1, "Mínimo 1 porción")
      .max(999, "Máximo 999 porciones"),
    difficulty: z.enum(PRODUCT_DIFFICULTIES, { message: "Dificultad inválida" }),
    recipe: z
      .array(recipeItemSchema)
      .min(1, "La receta necesita al menos un insumo"),
  })
  .strict();

export type ProductFormValues = z.infer<typeof productFormSchema>;

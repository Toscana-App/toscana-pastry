import { z } from "zod";
import { INGREDIENT_UNITS, STOCK_REASONS } from "./types";


export const ingredientCreateSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Ingresá un nombre")
      .max(120, "Máximo 120 caracteres"),
    unit: z.enum(INGREDIENT_UNITS, { message: "Unidad inválida" }),
    price_per_unit: z
      .number({ message: "Ingresá un precio válido" })
      .min(0, "No puede ser negativo")
      .max(100_000_000, "Valor demasiado alto"),
    stock_qty: z
      .number({ message: "Ingresá una cantidad válida" })
      .min(0, "No puede ser negativa")
      .max(100_000_000, "Valor demasiado alto"),
    low_stock_threshold: z
      .number({ message: "Ingresá un umbral válido" })
      .min(0, "No puede ser negativo")
      .max(100_000_000, "Valor demasiado alto"),
  })
  .strict();

export type IngredientCreateValues = z.infer<typeof ingredientCreateSchema>;

export const ingredientUpdateSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Ingresá un nombre")
      .max(120, "Máximo 120 caracteres")
      .optional(),
    unit: z.enum(INGREDIENT_UNITS, { message: "Unidad inválida" }).optional(),
    price_per_unit: z
      .number({ message: "Ingresá un precio válido" })
      .min(0, "No puede ser negativo")
      .max(100_000_000, "Valor demasiado alto")
      .optional(),
    low_stock_threshold: z
      .number({ message: "Ingresá un umbral válido" })
      .min(0, "No puede ser negativo")
      .max(100_000_000, "Valor demasiado alto")
      .optional(),
  })
  .strict()
  .refine((value) => Object.values(value).some((v) => v !== undefined), {
    message: "Modificá al menos un campo",
    path: ["name"],
  });

export type IngredientUpdateValues = z.infer<typeof ingredientUpdateSchema>;

export const stockAdjustSchema = z
  .object({
    delta: z
      .number({ message: "Ingresá una cantidad" })
      .refine((v) => v !== 0, "El ajuste no puede ser 0"),
    reason: z.enum(STOCK_REASONS, { message: "Motivo inválido" }),
    ref: z.string().max(120, "Máximo 120 caracteres").optional(),
  })
  .strict();

export type StockAdjustValues = z.infer<typeof stockAdjustSchema>;

export const importLinesSchema = z
  .array(z.string())
  .min(1, "Pegá al menos una línea")
  .max(500, "Máximo 500 líneas");

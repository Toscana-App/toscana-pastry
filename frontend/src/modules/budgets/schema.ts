import { z } from "zod";

/**
 * Schemas del wizard de presupuestos (Fase 7, P7/P8).
 *
 * Paso 1 (P7): cliente — nombre y teléfono (el dedupe del backend es por
 * nombre+teléfono, RF-P6-08; el dominio exige 5-20 dígitos). Sin email: el
 * modelo de cliente no lo tiene — el canal de contacto es WhatsApp.
 * Paso 2 (P8): líneas — producto + cantidad (mín. 1); precio manual opcional
 * solo en modo manual. Margen opcional 0–200 (mismo rango que el motor).
 */

/** Paso 1 — datos del cliente (RF-P7-01/02). */
export const budgetClientSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Nombre muy corto")
    .max(120),
  phone: z
    .string()
    .trim()
    .min(5, "Teléfono muy corto")
    .max(20)
    .regex(/^[0-9+\s-]+$/, "Solo dígitos"),
});

export type BudgetClientValue = z.infer<typeof budgetClientSchema>;

/** Línea del paso 2 (RF-P8-01). */
export const budgetItemInputSchema = z.object({
  product_id: z.string().min(1, "Elegí un producto"),
  qty: z
    .number({ message: "Cantidad inválida" })
    .int("Debe ser un entero")
    .min(1, "Mínimo 1")
    .max(99, "Máximo 99"),
  /** Vacío = precio del motor. En centavos. */
  price_override: z.union([
    z.literal(""),
    z.number().int("Solo enteros").min(1, "Mínimo $0.01"),
  ]),
});

export type BudgetItemInputValue = z.infer<typeof budgetItemInputSchema>;

/** Paso 2 — líneas + modo + margen. */
export const budgetItemsSchema = z.object({
  mode: z.enum(["cost_plus", "manual"]),
  /** Vacío = margen del tenant. */
  margin_pct: z.union([
    z.literal(""),
    z.number().min(0, "0% o más").max(200, "Máximo 200%"),
  ]),
  items: z
    .array(budgetItemInputSchema)
    .min(1, "Al menos un ítem"),
});

export type BudgetItemsValue = z.infer<typeof budgetItemsSchema>;

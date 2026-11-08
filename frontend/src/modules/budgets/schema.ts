import { z } from "zod";


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
  delivery_address: z
    .string()
    .trim()
    .max(500, "Dirección muy larga")
    .optional(),
});

export type BudgetClientValue = z.infer<typeof budgetClientSchema>;

export const budgetItemInputSchema = z.object({
  product_id: z.string().min(1, "Elegí un producto"),
  qty: z
    .number({ message: "Cantidad inválida" })
    .int("Debe ser un entero")
    .min(1, "Mínimo 1")
    .max(99, "Máximo 99"),
  price_override: z.union([
    z.literal(""),
    z.number().int("Solo enteros").min(1, "Mínimo $0.01"),
  ]),
});

export type BudgetItemInputValue = z.infer<typeof budgetItemInputSchema>;

export const budgetItemsSchema = z.object({
  mode: z.enum(["cost_plus", "manual"]),
  margin_pct: z.union([
    z.literal(""),
    z.number().min(0, "0% o más").max(200, "Máximo 200%"),
  ]),
  items: z
    .array(budgetItemInputSchema)
    .min(1, "Al menos un ítem"),
});

export type BudgetItemsValue = z.infer<typeof budgetItemsSchema>;

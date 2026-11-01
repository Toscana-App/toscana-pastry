import { z } from "zod";

/**
 * Schemas del wizard de pedidos (Fase 6, UC-02).
 *
 * Rango por línea: qty 1–99 (límite práctico del negocio), portions 1–999
 * (mismo techo que el backend: OrderItemInput), nota ≤ 200.
 * Margen opcional 0–200 (mismo rango que el motor de pricing).
 */

export const orderItemInputSchema = z.object({
  product_id: z.string().min(1, "Elegí un producto"),
  qty: z
    .number({ message: "Cantidad inválida" })
    .int("Debe ser un entero")
    .min(1, "Mínimo 1")
    .max(99, "Máximo 99"),
  /** null = porciones del producto (misma forma que el payload enviado). */
  portions: z.number().int().min(1, "Mínimo 1").max(999, "Máximo 999").nullable(),
  note: z.string().max(200, "Máximo 200 caracteres"),
});

export type OrderItemInputValue = z.infer<typeof orderItemInputSchema>;

export const orderCreateSchema = z.object({
  customer_id: z.string().min(1, "Elegí un cliente"),
  date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Fecha inválida")
    .refine((d) => !Number.isNaN(Date.parse(d)), "Fecha inválida"),
  /** null = margen del tenant; string numérico (porcentaje) = override. */
  margin_pct: z
    .string()
    .regex(/^\d+(\.\d+)?$/, "Margen inválido")
    .refine((v) => Number(v) <= 200, "Máximo 200%")
    .nullable(),
  items: z
    .array(orderItemInputSchema)
    .min(1, "Al menos un ítem"),
});

export type OrderCreateValue = z.infer<typeof orderCreateSchema>;

/** Cliente nuevo inline (wizard): nombre + teléfono. */
export const newCustomerSchema = z.object({
  name: z.string().trim().min(2, "Nombre muy corto").max(120),
  phone: z
    .string()
    .trim()
    .min(6, "Teléfono muy corto")
    .max(20)
    .regex(/^[0-9+\s-]+$/, "Solo dígitos"),
});

export type NewCustomerValue = z.infer<typeof newCustomerSchema>;

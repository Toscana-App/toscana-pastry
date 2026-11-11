import { z } from "zod";
import type { InvoiceCreatePayload, InvoiceItemPayload } from "./types";

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Ítem de la factura (lectura pre-cargada desde el pedido en v1). Se valida por
 * si el payload llega armado con items; los montos están en centavos.
 */
export const invoiceItemPayloadSchema = z
  .object({
    descripcion: z
      .string()
      .trim()
      .min(1, "Descripción requerida")
      .max(200, "Máximo 200 caracteres"),
    cantidad: z
      .number({ message: "Cantidad inválida" })
      .int("La cantidad debe ser un entero")
      .min(1, "Mínimo 1"),
    precio_unit: z
      .number({ message: "Precio inválido" })
      .min(0, "Mínimo 0"),
  })
  .strict();

/**
 * Schema del formulario de emisión de factura.
 *
 * Reglas:
 * - concepto 2 o 3 exige fch_serv_desde y fch_serv_hasta.
 * - doc_tipo 99 (Consumidor Final) fuerza doc_nro a 0.
 * - doc_tipo 80 (CUIT) / 86 (DNI) exige un número válido (1-11 dígitos).
 *
 * El output (transform) es el payload exacto de POST /api/v1/invoices, ya con
 * doc_nro normalizado a 0 para consumidor final y sin fechas para concepto 1.
 */
export const invoiceCreateSchema = z
  .object({
    order_id: z.string().min(1, "Pedido inválido"),
    concepto: z.union(
      [z.literal(1), z.literal(2), z.literal(3)],
      { message: "Concepto inválido" }
    ),
    fch_serv_desde: z.string().regex(DATE_RE, "Fecha inválida").nullable(),
    fch_serv_hasta: z.string().regex(DATE_RE, "Fecha inválida").nullable(),
    doc_tipo: z.union(
      [z.literal(99), z.literal(80), z.literal(86)],
      { message: "Tipo de documento inválido" }
    ),
    doc_nro: z
      .number({ message: "Número inválido" })
      .int("El número debe ser un entero")
      .min(0, "Mínimo 0")
      .max(99_999_999_999, "Máximo 11 dígitos"),
    receptor_nombre: z
      .string()
      .trim()
      .min(1, "Ingresá el nombre del receptor")
      .max(120, "Máximo 120 caracteres"),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.concepto === 2 || value.concepto === 3) {
      if (!value.fch_serv_desde) {
        ctx.addIssue({
          code: "custom",
          path: ["fch_serv_desde"],
          message: "Fecha inicial del servicio obligatoria",
        });
      }
      if (!value.fch_serv_hasta) {
        ctx.addIssue({
          code: "custom",
          path: ["fch_serv_hasta"],
          message: "Fecha final del servicio obligatoria",
        });
      }
    }
  })
  .transform((value): InvoiceCreatePayload => {
    const payload: InvoiceCreatePayload = {
      order_id: value.order_id,
      concepto: value.concepto,
      doc_tipo: value.doc_tipo,
      doc_nro: value.doc_tipo === 99 ? 0 : value.doc_nro,
      receptor_nombre: value.receptor_nombre,
    };
    if (value.concepto === 2 || value.concepto === 3) {
      payload.fch_serv_desde = value.fch_serv_desde ?? undefined;
      payload.fch_serv_hasta = value.fch_serv_hasta ?? undefined;
    }
    return payload;
  });

/** Valores que maneja react-hook-form (input del schema). */
export type InvoiceFormValues = z.input<typeof invoiceCreateSchema>;
/** Payload final que se envía al backend (output del transform). */
export type InvoicePayload = z.output<typeof invoiceCreateSchema>;

export type { InvoiceItemPayload };

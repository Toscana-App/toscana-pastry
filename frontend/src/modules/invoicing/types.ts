import type { OrderStatus } from "@/modules/orders/types";

/** Conceptos de facturación AFIP. */
export const INVOICE_CONCEPTS = [1, 2, 3] as const;
export type InvoiceConcept = (typeof INVOICE_CONCEPTS)[number];

/** Tipos de documento del receptor. */
export const INVOICE_DOC_TYPES = [99, 80, 86] as const;
export type InvoiceDocType = (typeof INVOICE_DOC_TYPES)[number];

/** Etiquetas de UI para los conceptos (1 productos / 2 servicios / 3 ambos). */
export const CONCEPT_LABELS: Record<InvoiceConcept, string> = {
  1: "Productos",
  2: "Servicios",
  3: "Productos y servicios",
};

/** Etiquetas de UI para los tipos de documento del receptor. */
export const DOC_TYPE_LABELS: Record<InvoiceDocType, string> = {
  99: "Consumidor Final",
  80: "CUIT",
  86: "DNI",
};

export type InvoiceState = "A" | "R";

/** Ítem del payload de facturación (montos en centavos, como el resto del sistema). */
export interface InvoiceItemPayload {
  descripcion: string;
  cantidad: number;
  precio_unit: number;
}

/** Body de POST /api/v1/invoices. Los montos NO se envían: el total sale del pedido. */
export interface InvoiceCreatePayload {
  order_id: string;
  concepto: InvoiceConcept;
  /** Solo para concepto 2/3. ISO yyyy-mm-dd. */
  fch_serv_desde?: string;
  /** Solo para concepto 2/3. ISO yyyy-mm-dd. */
  fch_serv_hasta?: string;
  doc_tipo: InvoiceDocType;
  doc_nro: number;
  receptor_nombre: string;
  items?: InvoiceItemPayload[];
}

/** Comprobante emitido (respuesta 201 de POST /api/v1/invoices). */
export interface Invoice {
  id: string;
  order_id: string;
  punto_venta: number;
  tipo_cbte: number;
  numero: number;
  cae: string;
  /** ISO datetime: vencimiento del CAE. */
  cae_vto: string;
  /** ISO datetime. */
  fecha: string;
  /** En centavos. */
  imp_total: number;
  estado: InvoiceState;
  pdf_url: string;
}

/**
 * Comprobante a mostrar en la UI. `punto_venta` es `number | null` porque cuando
 * el comprobante llega desde el detalle del pedido (tras recargar) ese campo no
 * se expone; recién se conoce tras la emisión (201).
 */
export interface InvoiceComprobante {
  punto_venta: number | null;
  numero: number;
  cae: string;
  cae_vto: string;
  pdf_url: string;
  /** Presente sólo tras la emisión local (201); se usa para el PDF por id. */
  id?: string;
}

/**
 * Un pedido es facturable cuando ya está entregado O pagado.
 * La emisión además requiere que no tenga comprobante (invoice === null).
 */
export function isFacturable(status: OrderStatus, paid: boolean): boolean {
  return status === "entregado" || paid;
}

/**
 * Formatea el comprobante como `{punto_venta}-{numero}` con el numero a 8 ceros
 * (ej. "0003-00000001"). Si el punto de venta no se conoce (recargado desde el
 * detalle) devuelve solo el numero a 8 ceros.
 */
export function comprobanteLabel(c: Pick<InvoiceComprobante, "punto_venta" | "numero">): string {
  const numero = String(c.numero).padStart(8, "0");
  if (c.punto_venta == null) return numero;
  return `${String(c.punto_venta).padStart(4, "0")}-${numero}`;
}

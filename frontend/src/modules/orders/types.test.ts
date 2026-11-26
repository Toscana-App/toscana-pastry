import { describe, expect, it } from "vitest";
import {
  ALLOWED_TRANSITIONS,
  ORDER_STATUS_LABELS,
  ORDER_STATUSES,
  type OrderStatus,
} from "./types";

/**
 * Mirror de la máquina de dominio (backend/src/domain/order_states.py).
 * Si la tabla cambia en el backend, este test fuerza a actualizar el
 * espejo frontend en el mismo cambio.
 */
const DOMAIN_MATRIX: Record<OrderStatus, readonly OrderStatus[]> = {
  new: ["confirmed"],
  confirmed: ["preparing", "cancelled"],
  preparing: ["pending_delivery", "cancelled"],
  pending_delivery: ["delivered"],
  delivered: [],
  cancelled: [],
};

describe("contrato de status de pedidos (mirror del dominio)", () => {
  it("ORDER_STATUSES: los 6 valores en inglés snake_case", () => {
    expect(ORDER_STATUSES).toEqual([
      "new",
      "confirmed",
      "preparing",
      "pending_delivery",
      "delivered",
      "cancelled",
    ]);
  });

  it("ALLOWED_TRANSITIONS espeja la matriz de la máquina de dominio", () => {
    expect(ALLOWED_TRANSITIONS).toEqual(DOMAIN_MATRIX);
  });

  it("los terminales no tienen salidas", () => {
    expect(ALLOWED_TRANSITIONS.delivered).toEqual([]);
    expect(ALLOWED_TRANSITIONS.cancelled).toEqual([]);
  });

  it("ORDER_STATUS_LABELS: español para la UI, con los dos nuevos estados", () => {
    expect(ORDER_STATUS_LABELS).toEqual({
      new: "Nuevo",
      confirmed: "Confirmado",
      preparing: "Pendiente preparación",
      pending_delivery: "Pendiente entrega",
      delivered: "Entregado",
      cancelled: "Cancelado",
    });
  });
});

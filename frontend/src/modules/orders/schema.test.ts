import { describe, expect, it } from "vitest";
import { orderCreateSchema } from "./schema";
import type { OrderCreatePayload } from "./types";

const base: OrderCreatePayload = {
  customer_id: "c1",
  date: "2026-10-01",
  margin_pct: null,
  items: [{ product_id: "p1", qty: 2, portions: null, note: "" }],
};

describe("orderCreateSchema (payload real del wizard)", () => {
  it("acepta porciones vacías (null) y margen del negocio (null)", () => {
    expect(orderCreateSchema.safeParse(base).success).toBe(true);
  });

  it("acepta un margen override como string numérico", () => {
    const res = orderCreateSchema.safeParse({ ...base, margin_pct: "20" });
    expect(res.success).toBe(true);
    expect(orderCreateSchema.safeParse({ ...base, margin_pct: "12.5" }).success).toBe(true);
  });

  it("rechaza margen > 200 o no numérico", () => {
    expect(orderCreateSchema.safeParse({ ...base, margin_pct: "201" }).success).toBe(false);
    expect(orderCreateSchema.safeParse({ ...base, margin_pct: "abc" }).success).toBe(false);
  });

  it("acepta porciones numéricas y rechaza fuera de rango", () => {
    const withPortions = (portions: number) => ({
      ...base,
      items: [{ product_id: "p1", qty: 1, portions, note: "" }],
    });
    expect(orderCreateSchema.safeParse(withPortions(12)).success).toBe(true);
    expect(orderCreateSchema.safeParse(withPortions(0)).success).toBe(false);
    expect(orderCreateSchema.safeParse(withPortions(1000)).success).toBe(false);
  });

  it("rechaza pedido sin ítems", () => {
    expect(orderCreateSchema.safeParse({ ...base, items: [] }).success).toBe(false);
  });
});

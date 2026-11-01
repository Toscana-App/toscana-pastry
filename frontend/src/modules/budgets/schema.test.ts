import { describe, expect, it } from "vitest";
import { budgetClientSchema, budgetItemsSchema } from "./schema";

/**
 * Tests de los schemas del wizard (Fase 7, P7/P8): validaciones de cliente,
 * líneas, modo y margen — espejo de las restricciones del dominio backend.
 */

describe("budgetClientSchema", () => {
  it("acepta nombre + teléfono válidos", () => {
    const res = budgetClientSchema.safeParse({ name: "María", phone: "11-2233-4455" });
    expect(res.success).toBe(true);
  });

  it("rejeca nombre vacío/corto y teléfono corto", () => {
    expect(budgetClientSchema.safeParse({ name: "M", phone: "11-2233-4455" }).success).toBe(false);
    expect(budgetClientSchema.safeParse({ name: "María", phone: "11" }).success).toBe(false);
    expect(budgetClientSchema.safeParse({ name: "", phone: "" }).success).toBe(false);
  });

  it("rechaza teléfono con letras", () => {
    const res = budgetClientSchema.safeParse({ name: "María", phone: "11-22a3-4455" });
    expect(res.success).toBe(false);
  });
});

describe("budgetItemsSchema", () => {
  const base = {
    mode: "cost_plus" as const,
    margin_pct: "",
    items: [{ product_id: "p1", qty: 1, price_override: "" }],
  };

  it("acepta cost_plus con margen vacío (margen del tenant)", () => {
    expect(budgetItemsSchema.safeParse(base).success).toBe(true);
  });

  it("acepta manual con overrides en centavos y precio de motor ('')", () => {
    const res = budgetItemsSchema.safeParse({
      mode: "manual",
      margin_pct: "",
      items: [
        { product_id: "p1", qty: 2, price_override: 120000 },
        { product_id: "p2", qty: 1, price_override: "" },
      ],
    });
    expect(res.success).toBe(true);
  });

  it("exige al menos un ítem y un producto elegido", () => {
    expect(budgetItemsSchema.safeParse({ ...base, items: [] }).success).toBe(false);
    expect(
      budgetItemsSchema.safeParse({ ...base, items: [{ product_id: "", qty: 1, price_override: "" }] })
        .success,
    ).toBe(false);
  });

  it("valida cantidad: entero, mínimo 1, máximo 99", () => {
    const withQty = (qty: number) =>
      budgetItemsSchema.safeParse({ ...base, items: [{ product_id: "p1", qty, price_override: "" }] });
    expect(withQty(0).success).toBe(false);
    expect(withQty(100).success).toBe(false);
    expect(withQty(2.5).success).toBe(false);
    expect(withQty(2).success).toBe(true);
  });

  it("valida margen: 0–200, vacío permitido", () => {
    const withMargin = (margin_pct: string | number) =>
      budgetItemsSchema.safeParse({ ...base, margin_pct });
    expect(withMargin(-1).success).toBe(false);
    expect(withMargin(201).success).toBe(false);
    expect(withMargin(200).success).toBe(true);
    expect(withMargin(0).success).toBe(true);
  });

  it("rechaza modo desconocido", () => {
    expect(budgetItemsSchema.safeParse({ ...base, mode: "auto" as never }).success).toBe(false);
  });
});

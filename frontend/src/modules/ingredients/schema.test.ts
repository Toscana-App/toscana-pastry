import { describe, expect, it } from "vitest";
import {
  importLinesSchema,
  ingredientCreateSchema,
  ingredientUpdateSchema,
  stockAdjustSchema,
} from "./schema";
import { INGREDIENT_UNITS, STOCK_REASONS, statusOf } from "./types";

describe("ingredientCreateSchema (RF-P2-02)", () => {
  const valid = {
    name: "Harina 0000",
    unit: "kg" as const,
    price_per_unit: 1200,
    stock_qty: 10,
    low_stock_threshold: 2,
  };

  it("acepta un payload válido", () => {
    expect(ingredientCreateSchema.safeParse(valid).success).toBe(true);
  });

  it("rechaza nombre vacío o solo espacios", () => {
    expect(ingredientCreateSchema.safeParse({ ...valid, name: "" }).success).toBe(false);
    expect(ingredientCreateSchema.safeParse({ ...valid, name: "   " }).success).toBe(false);
  });

  it("rechaza nombre de más de 120 caracteres", () => {
    const result = ingredientCreateSchema.safeParse({ ...valid, name: "a".repeat(121) });
    expect(result.success).toBe(false);
  });

  it("rechaza unidad fuera del contrato", () => {
    const result = ingredientCreateSchema.safeParse({ ...valid, unit: "litros" });
    expect(result.success).toBe(false);
  });

  it("acepta todas las unidades del contrato", () => {
    for (const unit of INGREDIENT_UNITS) {
      expect(ingredientCreateSchema.safeParse({ ...valid, unit }).success).toBe(true);
    }
  });

  it("rechaza precio y stock negativos", () => {
    expect(ingredientCreateSchema.safeParse({ ...valid, price_per_unit: -1 }).success).toBe(false);
    expect(ingredientCreateSchema.safeParse({ ...valid, stock_qty: -1 }).success).toBe(false);
    expect(
      ingredientCreateSchema.safeParse({ ...valid, low_stock_threshold: -1 }).success,
    ).toBe(false);
  });

  it("rechaza NaN (input numérico borrado)", () => {
    const result = ingredientCreateSchema.safeParse({ ...valid, price_per_unit: Number.NaN });
    expect(result.success).toBe(false);
  });

  it("rechaza campos desconocidos (extra=forbid en el backend)", () => {
    const result = ingredientCreateSchema.safeParse({ ...valid, status: "OK" });
    expect(result.success).toBe(false);
  });
});

describe("ingredientUpdateSchema (PATCH parcial)", () => {
  it("acepta un solo campo", () => {
    expect(ingredientUpdateSchema.safeParse({ price_per_unit: 900 }).success).toBe(true);
  });

  it("rechaza payload vacío (al menos un campo)", () => {
    expect(ingredientUpdateSchema.safeParse({}).success).toBe(false);
  });

  it("no permite tocar el stock (se ajusta como movimiento)", () => {
    expect(ingredientUpdateSchema.safeParse({ stock_qty: 5 }).success).toBe(false);
  });
});

describe("stockAdjustSchema (RF-P2-03)", () => {
  it("acepta delta positivo o negativo con motivo válido", () => {
    expect(stockAdjustSchema.safeParse({ delta: 2, reason: "compra" }).success).toBe(true);
    expect(stockAdjustSchema.safeParse({ delta: -1.5, reason: "merma" }).success).toBe(true);
  });

  it("rechaza delta 0", () => {
    const result = stockAdjustSchema.safeParse({ delta: 0, reason: "ajuste" });
    expect(result.success).toBe(false);
  });

  it("rechaza motivos fuera del contrato (compra | merma | ajuste)", () => {
    expect(stockAdjustSchema.safeParse({ delta: 1, reason: "robo" }).success).toBe(false);
    expect(stockAdjustSchema.safeParse({ delta: 1, reason: "descarte" }).success).toBe(false);
    expect(stockAdjustSchema.safeParse({ delta: 1, reason: "inicial" }).success).toBe(false);
  });

  it("acepta todos los motivos del contrato", () => {
    for (const reason of STOCK_REASONS) {
      expect(stockAdjustSchema.safeParse({ delta: 1, reason }).success).toBe(true);
    }
  });

  it("la referencia es opcional y acotada a 120 caracteres", () => {
    expect(stockAdjustSchema.safeParse({ delta: 1, reason: "compra", ref: "Factura A" }).success).toBe(true);
    expect(
      stockAdjustSchema.safeParse({ delta: 1, reason: "compra", ref: "x".repeat(121) }).success,
    ).toBe(false);
  });
});

describe("importLinesSchema (RF-P2-06)", () => {
  it("exige al menos una línea y no más de 500", () => {
    expect(importLinesSchema.safeParse([]).success).toBe(false);
    expect(importLinesSchema.safeParse(["Harina;kg;1200"]).success).toBe(true);
    expect(importLinesSchema.safeParse(Array(500).fill("x")).success).toBe(true);
    expect(importLinesSchema.safeParse(Array(501).fill("x")).success).toBe(false);
  });
});

describe("statusOf (espejo de domain/stock.py)", () => {
  it("EMPTY en 0, LOW hasta el umbral, OK arriba del umbral", () => {
    expect(statusOf("0", "2")).toBe("EMPTY");
    expect(statusOf("1", "2")).toBe("LOW");
    expect(statusOf("2", "2")).toBe("LOW");
    expect(statusOf("3", "2")).toBe("OK");
  });

  it("con umbral 0, cualquier stock positivo es OK", () => {
    expect(statusOf("0.5", "0")).toBe("OK");
  });
});

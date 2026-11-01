import { describe, expect, it } from "vitest";
import { productFormSchema } from "./schema";

const VALID = {
  name: "Torta de chocolate",
  category: "Tortas",
  description: "",
  prep_time_min: 60,
  servings: 8,
  difficulty: "simple" as const,
  recipe: [{ ingredient_id: "harina", qty: 250, unit: "g" as const }],
};

describe("productFormSchema", () => {
  it("acepta un producto válido con receta", () => {
    expect(productFormSchema.safeParse(VALID).success).toBe(true);
  });

  it("exige al menos un insumo en la receta (RF-P4-06)", () => {
    const result = productFormSchema.safeParse({ ...VALID, recipe: [] });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].message).toBe(
        "La receta necesita al menos un insumo",
      );
    }
  });

  it("rechaza cantidades <= 0 en la receta", () => {
    const result = productFormSchema.safeParse({
      ...VALID,
      recipe: [{ ingredient_id: "harina", qty: 0, unit: "g" }],
    });
    expect(result.success).toBe(false);
  });

  it("rechaza unidades fuera del contrato", () => {
    const result = productFormSchema.safeParse({
      ...VALID,
      recipe: [{ ingredient_id: "harina", qty: 1, unit: "lb" }],
    });
    expect(result.success).toBe(false);
  });

  it("exige nombre de al menos 2 caracteres y categoría", () => {
    expect(productFormSchema.safeParse({ ...VALID, name: "T" }).success).toBe(
      false,
    );
    expect(
      productFormSchema.safeParse({ ...VALID, category: " " }).success,
    ).toBe(false);
  });

  it("exige tiempo de preparación > 0 (RF-P4-06)", () => {
    expect(
      productFormSchema.safeParse({ ...VALID, prep_time_min: 0 }).success,
    ).toBe(false);
  });

  it("rechaza campos desconocidos (extra=forbid del backend)", () => {
    const result = productFormSchema.safeParse({ ...VALID, price: 1500 });
    expect(result.success).toBe(false);
  });

  it("valida la dificultad contra el enum del contrato", () => {
    expect(
      productFormSchema.safeParse({ ...VALID, difficulty: "extremo" }).success,
    ).toBe(false);
  });
});

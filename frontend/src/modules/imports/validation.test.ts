import { describe, expect, it } from "vitest";
import {
  compareColumns,
  isDecimal,
  validateRowBasic,
  ENTITY_COLUMNS,
} from "./validation";
import type { ImportEntity } from "./types";


describe("compareColumns — set exacto, orden irrelevante (RF-CSV-13)", () => {
  it("acepta el mismo set aunque cambie el orden", () => {
    expect(compareColumns(["a", "b", "c"], ["c", "a", "b"])).toEqual({
      ok: true,
      missing: [],
      extra: [],
    });
  });

  it("marca columnas faltantes", () => {
    expect(compareColumns(["a", "b", "c"], ["a"])).toEqual({
      ok: false,
      missing: ["b", "c"],
      extra: [],
    });
  });

  it("marca columnas ajenas a la plantilla", () => {
    expect(compareColumns(["a", "b"], ["a", "b", "x"])).toEqual({
      ok: false,
      missing: [],
      extra: ["x"],
    });
  });

  it("combina faltantes y extras", () => {
    expect(compareColumns(["a", "b"], ["a", "x"])).toEqual({
      ok: false,
      missing: ["b"],
      extra: ["x"],
    });
  });
});

describe("isDecimal — convención argentina (coma decimal, punto miles)", () => {
  it("entero", () => expect(isDecimal("123")).toBe(true));
  it("coma decimal", () => expect(isDecimal("1,5")).toBe(true));
  it("punto miles + coma decimal", () => expect(isDecimal("1.234,56")).toBe(true));
  it("tolera punto decimal", () => expect(isDecimal("12.5")).toBe(true));
  it("espacios alrededor", () => expect(isDecimal("  10  ")).toBe(true));
  it("vacío → no", () => expect(isDecimal("")).toBe(false));
  it("letras → no", () => expect(isDecimal("abc")).toBe(false));
  it("mezcla → no", () => expect(isDecimal("12a3")).toBe(false));
});

describe("validateRowBasic — requeridos + numéricos por fila", () => {
  const spec = ENTITY_COLUMNS.ingredients;

  it("fila completa y válida no devuelve errores", () => {
    expect(
      validateRowBasic(spec, {
        nombre: "Harina",
        unidad: "kg",
        precio_por_unidad: "1.234,50",
        cantidad_inicial: "10",
        stock_minimo: "2",
      }),
    ).toEqual([]);
  });

  it("campo requerido vacío → error que menciona la columna", () => {
    const errs = validateRowBasic(spec, {
      nombre: "",
      unidad: "kg",
      precio_por_unidad: "10",
    });
    expect(errs.some((e) => e.includes("nombre"))).toBe(true);
  });

  it("numérico inválido → error que menciona la columna", () => {
    const errs = validateRowBasic(spec, {
      nombre: "Harina",
      unidad: "kg",
      precio_por_unidad: "abc",
    });
    expect(errs.some((e) => e.includes("precio_por_unidad"))).toBe(true);
  });

  it("campo opcional vacío no genera error", () => {
    expect(
      validateRowBasic(spec, {
        nombre: "H",
        unidad: "kg",
        precio_por_unidad: "1",
        cantidad_inicial: "",
        stock_minimo: "",
      }),
    ).toEqual([]);
  });
});

describe("ENTITY_COLUMNS — espejo de los adapters del backend", () => {
  it("define columnas para las 3 entidades", () => {
    const entities: ImportEntity[] = ["ingredients", "products", "customers"];
    for (const e of entities) {
      expect(ENTITY_COLUMNS[e].length).toBeGreaterThan(0);
      expect(ENTITY_COLUMNS[e].every((c) => c.key.length > 0)).toBe(true);
    }
  });

  it("coincide con el set de columnas de la plantilla de insumos", () => {
    expect(ENTITY_COLUMNS.ingredients.map((c) => c.key)).toEqual([
      "nombre",
      "unidad",
      "precio_por_unidad",
      "cantidad_inicial",
      "stock_minimo",
    ]);
  });
});

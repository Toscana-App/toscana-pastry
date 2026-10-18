import { describe, expect, it } from "vitest";
import { settingsSchema } from "./schema";
import { SETTINGS_DEFAULTS, toFormValues } from "./types";

const valid = { ...SETTINGS_DEFAULTS };

describe("settingsSchema (RF-P5-01/06)", () => {
  it("acepta los valores por defecto de fábrica", () => {
    expect(settingsSchema.safeParse(valid).success).toBe(true);
  });

  it("respeta los rangos del contrato", () => {
    expect(settingsSchema.safeParse({ ...valid, hourly_rate: 0 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, hourly_rate: 100_001 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, margin_pct: 101 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, round_step: 0 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, round_step: 1001 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, urgent_surcharge_pct: -1 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, default_prep_minutes: 1441 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, default_servings: 0 }).success).toBe(false);
  });

  it("minutos y porciones son enteros", () => {
    expect(settingsSchema.safeParse({ ...valid, default_prep_minutes: 12.5 }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, default_servings: 2.5 }).success).toBe(false);
  });

  it("RF-P5-06: gas_pct debe ser 0 si include_gas está apagado", () => {
    const result = settingsSchema.safeParse({ ...valid, include_gas: false, gas_pct: 3 });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path[0] === "gas_pct")).toBe(true);
    }
    expect(
      settingsSchema.safeParse({ ...valid, include_gas: false, gas_pct: 0 }).success,
    ).toBe(true);
  });

  it("RF-P5-06: waste_pct debe ser 0 si include_waste está apagado", () => {
    expect(
      settingsSchema.safeParse({ ...valid, include_waste: false, waste_pct: 3 }).success,
    ).toBe(false);
    expect(
      settingsSchema.safeParse({ ...valid, include_waste: false, waste_pct: 0 }).success,
    ).toBe(true);
  });

  it("rechaza dificultades fuera del contrato y campos desconocidos", () => {
    expect(settingsSchema.safeParse({ ...valid, default_difficulty: "dificil" }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, tenant_id: "x" }).success).toBe(false);
  });
});

describe("toFormValues", () => {
  it("convierte Money en centavos a pesos y Pct a number", () => {
    const form = toFormValues({
      hourly_rate: 300000,
      margin_pct: "30",
      round_step: 10000,
      include_labor: true,
      include_gas: true,
      gas_pct: "3",
      include_waste: false,
      waste_pct: "0",
      urgent_surcharge_pct: "20",
      default_prep_minutes: 30,
      default_servings: 6,
      default_difficulty: "simple",
    });

    expect(form.hourly_rate).toBe(3000);
    expect(form.margin_pct).toBe(30);
    expect(form.round_step).toBe(100);
    expect(form.gas_pct).toBe(3);
    expect(form.include_waste).toBe(false);
    expect(form.default_difficulty).toBe("simple");
  });
});

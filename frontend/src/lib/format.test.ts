import { describe, expect, it } from "vitest";
import {
  centsToPesos,
  formatCents,
  formatDateTime,
  formatMoney,
  formatPct,
  formatQty,
  formatSignedQty,
  pesosToCents,
} from "./format";

describe("formatMoney (RF-07: ARS, moneda mayúscula, prefijo, sin round propio)", () => {
  it("prefijo ARS + separador de miles con punto y moneda mayúscula", () => {
    expect(formatMoney("1200")).toBe("ARS 1.200");
    expect(formatMoney("1200000")).toBe("ARS 1.200.000");
  });

  it("acepta string (Money serializa como string en el backend)", () => {
    expect(formatMoney("1200.00")).toBe("ARS 1.200");
    expect(formatMoney(3500)).toBe("ARS 3.500");
  });

  it("redondea a peso entero para mostrar (sin centavos en ARS doméstico)", () => {
    expect(formatMoney("0.5")).toBe("ARS 1");
    expect(formatMoney("1200.4")).toBe("ARS 1.200");
  });

  it("inputs inválidos dan ARS 0, nunca NaN", () => {
    expect(formatMoney("")).toBe("ARS 0");
    expect(formatMoney("abc")).toBe("ARS 0");
    expect(formatMoney(Number.NaN)).toBe("ARS 0");
  });
});

describe("formatQty (cantidad como string, decimal con coma)", () => {
  it("enteros sin decimales", () => {
    expect(formatQty("5", "kg")).toBe("5 kg");
  });

  it("decimales con coma (es-AR)", () => {
    expect(formatQty("0.5", "kg")).toBe("0,5 kg");
    expect(formatQty("1.5", "unidad")).toBe("1,5 unidad");
  });

  it("input inválido da 0", () => {
    expect(formatQty("", "kg")).toBe("0 kg");
  });
});

describe("formatSignedQty (deltas de stock: signo, U+2212, sin -0)", () => {
  it("positivo con +", () => {
    expect(formatSignedQty("2")).toBe("+2");
    expect(formatSignedQty(1.5)).toBe("+1,5");
  });

  it("negativo con U+2212 (no guion ASCII)", () => {
    expect(formatSignedQty("-3")).toBe("−3");
  });

  it("cero y NaN dan 0 sin signo", () => {
    expect(formatSignedQty("0")).toBe("0");
    expect(formatSignedQty(0)).toBe("0");
    expect(formatSignedQty("abc")).toBe("0");
  });
});

describe("formatDateTime (ISO 8601 → dd/mm/yyyy hh:mm)", () => {
  it("convierte ISO a formato local en 24 h", () => {
    const formatted = formatDateTime("2026-10-16T14:30:00Z");
    expect(formatted).toMatch(/\d{2}\/\d{2}\/2026/);
    expect(formatted).toMatch(/\d{2}:\d{2}/);
    expect(formatted).not.toMatch(/a\.\s?m\.|p\.\s?m\./i);
  });

  it("input inválido da guion, no crash", () => {
    expect(formatDateTime("no es una fecha")).toBe("—");
  });
});

describe("formatCents (Money long: centavos → ARS)", () => {
  it("formatea centavos exactos", () => {
    expect(formatCents(310000)).toBe("ARS 3.100");
    expect(formatCents(310050)).toBe("ARS 3.100,5");
    expect(formatCents(100)).toBe("ARS 1");
  });

  it("input inválido da ARS 0, nunca NaN", () => {
    expect(formatCents(Number.NaN)).toBe("ARS 0");
  });
});

describe("pesosToCents / centsToPesos (borde de los formularios)", () => {
  it("pesos → centavos con aritmética exacta", () => {
    expect(pesosToCents(3000)).toBe(300000);
    expect(pesosToCents(3000.5)).toBe(300050);
    expect(pesosToCents("1200.25")).toBe(120025);
    expect(pesosToCents(0)).toBe(0);
  });

  it("centavos → pesos para precargar inputs", () => {
    expect(centsToPesos(300000)).toBe(3000);
    expect(centsToPesos(300050)).toBe(3000.5);
  });

  it("ida y vuelta sin pérdida", () => {
    expect(pesosToCents(centsToPesos(123456))).toBe(123456);
  });
});

describe("formatPct (porcentaje: no es Money, no lleva centavos)", () => {
  it("muestra el porcentaje directo", () => {
    expect(formatPct(100)).toBe("100%");
    expect(formatPct(1.5)).toBe("1,5%");
    expect(formatPct(0)).toBe("0%");
  });

  it("null/NaN dan 0%", () => {
    expect(formatPct(null)).toBe("0%");
  });
});

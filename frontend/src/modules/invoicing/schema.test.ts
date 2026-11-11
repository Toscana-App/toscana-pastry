import { describe, expect, it } from "vitest";
import { invoiceCreateSchema } from "./schema";

const base = {
  order_id: "o1",
  concepto: 1,
  fch_serv_desde: null,
  fch_serv_hasta: null,
  doc_tipo: 99,
  doc_nro: 0,
  receptor_nombre: "Cliente Test",
};

describe("invoiceCreateSchema — concepto y fechas", () => {
  it("concepto 1 (productos) sin fechas es válido", () => {
    expect(invoiceCreateSchema.safeParse(base).success).toBe(true);
  });

  it("concepto 2 sin fechas → inválido (fch_serv_desde/hasta requeridas)", () => {
    const res = invoiceCreateSchema.safeParse({ ...base, concepto: 2 });
    expect(res.success).toBe(false);
    if (!res.success) {
      const paths = res.error.issues.map((i) => i.path.join("."));
      expect(paths).toContain("fch_serv_desde");
      expect(paths).toContain("fch_serv_hasta");
    }
  });

  it("concepto 3 sin fechas → inválido", () => {
    expect(invoiceCreateSchema.safeParse({ ...base, concepto: 3 }).success).toBe(false);
  });

  it("concepto 2 con fechas válidas → válido y las incluye en el payload", () => {
    const res = invoiceCreateSchema.safeParse({
      ...base,
      concepto: 2,
      fch_serv_desde: "2026-11-01",
      fch_serv_hasta: "2026-11-05",
    });
    expect(res.success).toBe(true);
    if (res.success) {
      expect(res.data.fch_serv_desde).toBe("2026-11-01");
      expect(res.data.fch_serv_hasta).toBe("2026-11-05");
    }
  });

  it("concepto 1 no lleva fechas en el payload transformado", () => {
    const res = invoiceCreateSchema.safeParse(base);
    expect(res.success).toBe(true);
    if (res.success) {
      expect(res.data).not.toHaveProperty("fch_serv_desde");
      expect(res.data).not.toHaveProperty("fch_serv_hasta");
    }
  });

  it("concepto inválido → inválido", () => {
    expect(
      invoiceCreateSchema.safeParse({ ...base, concepto: 9 } as never).success
    ).toBe(false);
  });
});

describe("invoiceCreateSchema — receptor / doc_tipo", () => {
  it("doc_tipo 99 (Consumidor Final) fuerza doc_nro a 0", () => {
    const res = invoiceCreateSchema.safeParse({
      ...base,
      doc_tipo: 99,
      doc_nro: 12345,
    });
    expect(res.success).toBe(true);
    if (res.success) expect(res.data.doc_nro).toBe(0);
  });

  it("doc_tipo 80 (CUIT) conserva el número", () => {
    const res = invoiceCreateSchema.safeParse({
      ...base,
      doc_tipo: 80,
      doc_nro: 30123456789,
    });
    expect(res.success).toBe(true);
    if (res.success) expect(res.data.doc_nro).toBe(30123456789);
  });

  it("doc_tipo 86 (DNI) conserva el número", () => {
    const res = invoiceCreateSchema.safeParse({
      ...base,
      doc_tipo: 86,
      doc_nro: 12345678,
    });
    expect(res.success).toBe(true);
    if (res.success) expect(res.data.doc_nro).toBe(12345678);
  });

  it("doc_tipo inválido → inválido", () => {
    expect(
      invoiceCreateSchema.safeParse({ ...base, doc_tipo: 88 } as never).success
    ).toBe(false);
  });

  it("doc_nro negativo → inválido", () => {
    expect(
      invoiceCreateSchema.safeParse({ ...base, doc_nro: -5 }).success
    ).toBe(false);
  });

  it("receptor_nombre vacío → inválido", () => {
    expect(
      invoiceCreateSchema.safeParse({ ...base, receptor_nombre: "   " }).success
    ).toBe(false);
  });
});

describe("invoiceCreateSchema — output (payload)", () => {
  it("incluye order_id, concepto, receptor y normaliza doc_nro", () => {
    const res = invoiceCreateSchema.safeParse({
      ...base,
      doc_tipo: 80,
      doc_nro: 30123456789,
    });
    expect(res.success).toBe(true);
    if (res.success) {
      expect(res.data.order_id).toBe("o1");
      expect(res.data.concepto).toBe(1);
      expect(res.data.receptor_nombre).toBe("Cliente Test");
      expect(res.data.doc_nro).toBe(30123456789);
    }
  });
});

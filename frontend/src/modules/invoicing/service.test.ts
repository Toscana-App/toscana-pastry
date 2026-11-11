import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { invoicesService } from "./service";
import type { InvoiceCreatePayload } from "./types";

const API_BASE = "http://localhost:8000/api/v1";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastCall(fetchMock: ReturnType<typeof mockFetch>) {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return { url, init };
}

function invoiceBody(over: Record<string, unknown> = {}) {
  return {
    id: "inv1",
    order_id: "o1",
    punto_venta: 3,
    tipo_cbte: 11,
    numero: 1,
    cae: "12345678901234",
    cae_vto: "2026-11-21T12:00:00",
    fecha: "2026-11-11T12:00:00",
    imp_total: 1234500,
    estado: "A",
    pdf_url: "/api/v1/invoices/inv1/pdf",
    ...over,
  };
}

function payload(over: Partial<InvoiceCreatePayload> = {}): InvoiceCreatePayload {
  return {
    order_id: "o1",
    concepto: 1,
    doc_tipo: 99,
    doc_nro: 0,
    receptor_nombre: "Cliente Test",
    ...over,
  };
}

beforeEach(() => {
  document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete (URL as unknown as { createObjectURL?: unknown }).createObjectURL;
  delete (URL as unknown as { revokeObjectURL?: unknown }).revokeObjectURL;
});

describe("invoicesService — POST /invoices", () => {
  it("create mapea la respuesta 201 a un Invoice", async () => {
    const fetchMock = mockFetch(201, invoiceBody());

    const inv = await invoicesService.create(payload());

    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/invoices`);
    const { init } = lastCall(fetchMock);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(payload());
    expect(inv.id).toBe("inv1");
    expect(inv.punto_venta).toBe(3);
    expect(inv.tipo_cbte).toBe(11);
    expect(inv.numero).toBe(1);
    expect(inv.cae).toBe("12345678901234");
    expect(inv.cae_vto).toBe("2026-11-21T12:00:00");
    expect(inv.imp_total).toBe(1234500);
    expect(inv.estado).toBe("A");
    expect(inv.pdf_url).toBe("/api/v1/invoices/inv1/pdf");
  });

  it("create convierte punto_venta/numero/imp_total a número aunque lleguen como string", async () => {
    mockFetch(201, invoiceBody({ punto_venta: "3", numero: "7", imp_total: "99900" }));

    const inv = await invoicesService.create(payload());

    expect(inv.punto_venta).toBe(3);
    expect(inv.numero).toBe(7);
    expect(inv.imp_total).toBe(99900);
  });

  it("409 → error con status 409 (pedido ya facturado)", async () => {
    mockFetch(409, { detail: "El pedido ya tiene comprobante" });

    const p = invoicesService.create(payload());
    await expect(p).rejects.toMatchObject({ status: 409 });
  });

  it("503 → error con status 503 (facturación no configurada)", async () => {
    mockFetch(503, { detail: "Facturación no configurada" });

    await expect(invoicesService.create(payload())).rejects.toMatchObject({
      status: 503,
    });
  });

  it("422 → error con status 422 y mensaje de validación", async () => {
    mockFetch(422, {
      detail: [{ msg: "La fecha final no puede ser anterior a la inicial" }],
    });

    await expect(invoicesService.create(payload())).rejects.toThrow(
      "La fecha final no puede ser anterior a la inicial"
    );
  });

  it("400 → error con status 400 y las observaciones de ARCA", async () => {
    mockFetch(400, { detail: "Receptor inexistente en el dominio AFIP" });

    await expect(invoicesService.create(payload())).rejects.toThrow(
      "Receptor inexistente en el dominio AFIP"
    );
  });
});

describe("invoicesService — GET /invoices/{id}/pdf", () => {
  function mockBlobFetch(status: number, headers: Record<string, string> = {}) {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      headers: new Headers(headers),
      json: async () => null,
      blob: async () => new Blob(["%PDF-1.4 fake"]),
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  beforeEach(() => {
    URL.createObjectURL = vi.fn().mockReturnValue("blob:mock");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("downloadPdf con pdf_url relativo a la base API usa la URL correcta", async () => {
    const fetchMock = mockBlobFetch(200, {
      "Content-Disposition": 'attachment; filename="factura-0003-00000001.pdf"',
    });

    await invoicesService.downloadPdf("/api/v1/invoices/inv1/pdf");

    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/invoices/inv1/pdf`);
  });

  it("downloadPdf normaliza un pdf_url absoluto a la ruta relativa", async () => {
    const fetchMock = mockBlobFetch(200);

    await invoicesService.downloadPdf(`${API_BASE}/invoices/inv1/pdf`);

    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/invoices/inv1/pdf`);
  });

  it("downloadPdf con pdf_url relativo sin base API funciona igual", async () => {
    const fetchMock = mockBlobFetch(200);

    await invoicesService.downloadPdf("/invoices/inv1/pdf");

    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/invoices/inv1/pdf`);
  });

  it("downloadPdf: respuesta no ok → error con el detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: "Comprobante no encontrado" }) })
    );

    await expect(invoicesService.downloadPdf("/api/v1/invoices/inv1/pdf")).rejects.toThrow(
      "Comprobante no encontrado"
    );
  });
});

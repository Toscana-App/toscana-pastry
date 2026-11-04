import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { budgetsService } from "./service";

/**
 * Tests del service de presupuestos (Fase 7, P7/P8): verifican el contrato
 * HTTP (path, método, body) contra `backend/src/api/v1/budgets/schemas.py`
 * y el contrato Money long de centavos (RF-P8-03). Se mockea fetch — nada de red.
 *
 * Money: la API emite y recibe centavos; el service los pasa tal cual.
 * Margen: string numérico en el wire ("100" = 100%), number|null en el tipo.
 */
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

/** Detalle válido mínimo para mockear las respuestas del CRUD. */
function detailBody(over: Record<string, unknown> = {}) {
  return {
    id: "b1",
    seq: "#00001",
    customer: { id: "c1", name: "María", phone: "11-2233-4455" },
    status: "borrador",
    calculation_mode: "cost_plus",
    margin_pct: "100",
    version: 1,
    items: [
      {
        product_id: "p1",
        product_name: "Torta de Limón",
        qty: 2,
        unit_cost: 77500,
        unit_selling: 155000,
        line_cost: 155000,
        line_selling: 310000,
        price_overridden: false,
      },
    ],
    summary: { subtotal: 310000, total_costos: 155000, ganancia: 155000, total_venta: 375100 },
    created_at: "2026-10-01T12:00:00Z",
    updated_at: "2026-10-01T12:00:00Z",
    sent_at: null,
    ...over,
  };
}

beforeEach(() => {
  document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("budgetsService — GET /budgets", () => {
  it("list arma el querystring con los alias del backend (from/to)", async () => {
    const fetchMock = mockFetch(200, {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    await budgetsService.list({
      q: "0002",
      status: "enviado",
      from: "2026-10-01",
      to: "2026-10-31",
      page: 2,
      page_size: 20,
    });
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/budgets?q=0002&status=enviado&from=2026-10-01&to=2026-10-31&page=2&page_size=20`,
    );

    await budgetsService.list();
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets`);
  });
});

describe("budgetsService — GET /budgets/{id}", () => {
  it("getDetail mapea centavos, margen string→number e items", async () => {
    const fetchMock = mockFetch(200, detailBody());

    const detail = await budgetsService.getDetail("b1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets/b1`);
    expect(detail.seq).toBe("#00001");
    expect(detail.margin_pct).toBe(100);
    expect(detail.items[0].unit_cost).toBe(77500);
    expect(detail.items[0].unit_selling).toBe(155000);
    expect(detail.summary.total_venta).toBe(375100);
    expect(detail.sent_at).toBeNull();
  });

  it("getDetail: margin_pct null (margen del tenant) y price_overridden ausente → false", async () => {
    mockFetch(200,
      detailBody({
        margin_pct: null,
        items: [
          {
            product_id: "p1",
            product_name: "Torta",
            qty: 1,
            unit_cost: 77500,
            unit_selling: 155000,
            line_cost: 77500,
            line_selling: 155000,
          },
        ],
      }),
    );

    const detail = await budgetsService.getDetail("b1");
    expect(detail.margin_pct).toBeNull();
    expect(detail.items[0].price_overridden).toBe(false);
  });
});

describe("budgetsService — POST /budgets", () => {
  it("create manda centavos de price_override y omite el campo cuando es null", async () => {
    const fetchMock = mockFetch(201, detailBody());

    await budgetsService.create({
      customer_id: "c1",
      calculation_mode: "manual",
      margin_pct: null,
      items: [
        { product_id: "p1", qty: 2, price_override: null },
        { product_id: "p2", qty: 1, price_override: 120000 },
      ],
    });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/budgets`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      customer_id: "c1",
      calculation_mode: "manual",
      margin_pct: null,
      items: [
        { product_id: "p1", qty: 2 },
        { product_id: "p2", qty: 1, price_override: 120000 },
      ],
    });
  });
});

describe("budgetsService — PUT /budgets/{id}", () => {
  it("update manda solo los campos presentes (margin_pct undefined no se toca)", async () => {
    const fetchMock = mockFetch(200, detailBody());

    await budgetsService.update("b1", {
      items: [{ product_id: "p1", qty: 3, price_override: null }],
    });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/budgets/b1`);
    expect(init.method).toBe("PUT");
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ items: [{ product_id: "p1", qty: 3 }] });
    expect(body.margin_pct).toBeUndefined();
  });

  it("update con margin_pct null lo manda explícito (vuelve a margen del tenant)", async () => {
    const fetchMock = mockFetch(200, detailBody());

    await budgetsService.update("b1", { calculation_mode: "cost_plus", margin_pct: null });

    const body = JSON.parse(lastCall(fetchMock).init.body as string);
    expect(body).toEqual({ calculation_mode: "cost_plus", margin_pct: null });
  });
});

describe("budgetsService — acciones", () => {
  it("recalculate hace POST a /recalculate y mapea el resumen", async () => {
    const fetchMock = mockFetch(200, {
      summary: { subtotal: 310000, total_costos: 155000, ganancia: 155000, total_venta: 375100 },
      margin_applied: "100",
    });

    const res = await budgetsService.recalculate("b1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets/b1/recalculate`);
    expect(res.margin_applied).toBe(100);
    expect(res.summary.subtotal).toBe(310000);
  });

  it("send hace POST a /send", async () => {
    const fetchMock = mockFetch(200, detailBody({ status: "enviado", sent_at: "2026-10-02T10:00:00Z" }));

    const sent = await budgetsService.send("b1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets/b1/send`);
    expect(sent.status).toBe("enviado");
    expect(sent.sent_at).toBe("2026-10-02T10:00:00Z");
  });

  it("convertToOrder hace POST a /convert-to-order y devuelve order_id", async () => {
    const fetchMock = mockFetch(200, { order_id: "o9", message: "Pedido creado" });

    const res = await budgetsService.convertToOrder("b1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets/b1/convert-to-order`);
    expect(res.order_id).toBe("o9");
  });

  it("remove hace DELETE y tolera 204 sin cuerpo", async () => {
    const fetchMock = mockFetch(204, undefined);

    await expect(budgetsService.remove("b1")).resolves.toBeUndefined();
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/budgets/b1`);
    expect(init.method).toBe("DELETE");
  });
});

describe("budgetsService — GET /budgets/export (Fase 5)", () => {
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
    // jsdom no implementa object URLs.
    URL.createObjectURL = vi.fn().mockReturnValue("blob:mock");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("exportReport csv arma la URL con filtros y format=csv", async () => {
    const fetchMock = mockBlobFetch(200, {
      "Content-Disposition": 'attachment; filename="presupuestos.csv"',
    });

    await budgetsService.exportReport(
      { status: "enviado", from: "2026-10-01", to: "2026-10-31" },
      "csv",
    );

    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/budgets/export?status=enviado&from=2026-10-01&to=2026-10-31&format=csv`,
    );
  });

  it("exportReport pdf usa format=pdf y sin filtros no manda query extra", async () => {
    const fetchMock = mockBlobFetch(200, {
      "Content-Disposition": 'attachment; filename="presupuestos.pdf"',
    });

    await budgetsService.exportReport({}, "pdf");

    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/budgets/export?format=pdf`);
  });
});

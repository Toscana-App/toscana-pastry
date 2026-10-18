import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  customersService,
  insufficientStockOf,
  ordersService,
} from "./service";

/**
 * Tests del service de pedidos (Fase 6): verifican el contrato HTTP
 * (path, método, body) y la conversión Money string → long de centavos.
 * Se mockea fetch — nada de red.
 *
 * Money: la API emite string ("3100.00"); el service lo convierte a long
 * (310000). Margen: porcentaje plano ("100" = 100%), no money.
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

beforeEach(() => {
  document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ordersService — GET /orders", () => {
  it("list arma el querystring solo con los filtros presentes", async () => {
    const fetchMock = mockFetch(200, {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    await ordersService.list({
      status: "nuevo",
      q: "maria",
      date_from: "2026-10-01",
      page: 2,
      page_size: 20,
    });
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/orders?status=nuevo&q=maria&date_from=2026-10-01&page=2&page_size=20`,
    );

    await ordersService.list();
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/orders`);
  });

  it("list convierte total de string a long de centavos", async () => {
    const fetchMock = mockFetch(200, {
      items: [
        {
          id: "o1",
          customer_id: "c1",
          customer_name: "María",
          customer_phone: "11-2233-4455",
          date: "2026-10-01",
          status: "nuevo",
          item_count: 2,
          total: "3100.00",
          created_at: "2026-10-01T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });

    const res = await ordersService.list();
    expect(res.items[0].total).toBe(310000);
    expect(res.total).toBe(1);
  });
});

describe("ordersService — GET /orders/{id}", () => {
  it("getDetail convierte montos, margen y líneas del snapshot", async () => {
    const fetchMock = mockFetch(200, {
      id: "o1",
      customer: { id: "c1", name: "María", phone: "11-2233-4455" },
      date: "2026-10-01",
      status: "confirmado",
      margin_pct: "100",
      items: [
        {
          product_id: "p1",
          product_name: "Torta de Limón",
          qty: 2,
          portions: 6,
          note: "sin azúcar",
          complete: true,
          missing_ingredients: [],
          price: {
            materials: "700.00",
            waste: "50.00",
            materials_con_merma: "750.00",
            labor: "55.00",
            gas: "0.00",
            base: "775.00",
            margin_pct: "100",
            final: "1550.00",
            rounded: "1550",
          },
          lines: [
            {
              ingredient_id: "i1",
              ingredient_name: "Harina 000",
              qty: "0.25",
              unit: "kg",
              cost: "280.00",
            },
          ],
          rounded: "3100",
        },
      ],
      total: "3100.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-01T12:00:00Z",
      updated_at: "2026-10-01T12:05:00Z",
    });

    const detail = await ordersService.getDetail("o1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/orders/o1`);
    expect(detail.total).toBe(310000);
    expect(detail.margin_pct).toBe(100);
    expect(detail.items[0].price.base).toBe(77500);
    expect(detail.items[0].price.margin_pct).toBe(100);
    expect(detail.items[0].price.final).toBe(155000);
    expect(detail.items[0].rounded).toBe(310000);
    expect(detail.items[0].lines[0].cost).toBe(28000);
    expect(detail.items[0].lines[0].is_missing).toBe(false);
  });

  it("getDetail: margin_pct null queda null (margen del tenant)", async () => {
    const fetchMock = mockFetch(200, {
      id: "o2",
      customer: { id: "c1", name: "María", phone: "11" },
      date: "2026-10-01",
      status: "nuevo",
      margin_pct: null,
      items: [],
      total: "0.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-01T12:00:00Z",
      updated_at: "2026-10-01T12:00:00Z",
    });

    const detail = await ordersService.getDetail("o2");
    expect(detail.margin_pct).toBeNull();
  });
});

describe("ordersService — POST /orders", () => {
  it("create manda el payload con margin_pct string y convierte la respuesta", async () => {
    const fetchMock = mockFetch(201, {
      id: "o9",
      customer: { id: "c1", name: "María", phone: "11" },
      date: "2026-10-02",
      status: "nuevo",
      margin_pct: null,
      items: [],
      total: "1550.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-02T09:00:00Z",
      updated_at: "2026-10-02T09:00:00Z",
    });

    const detail = await ordersService.create({
      customer_id: "c1",
      date: "2026-10-02",
      margin_pct: null,
      items: [
        { product_id: "p1", qty: 2, portions: null, note: "" },
        { product_id: "p2", qty: 1, portions: 4, note: "con chocolate" },
      ],
    });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/orders`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      customer_id: "c1",
      date: "2026-10-02",
      margin_pct: null,
      items: [
        { product_id: "p1", qty: 2, note: "" },
        { product_id: "p2", qty: 1, portions: 4, note: "con chocolate" },
      ],
    });
    expect(detail.total).toBe(155000);
  });

  it("create con margin_pct lo pasa como string numérico", async () => {
    const fetchMock = mockFetch(201, {
      id: "o9",
      customer: { id: "c1", name: "María", phone: "11" },
      date: "2026-10-02",
      status: "nuevo",
      margin_pct: "175",
      items: [],
      total: "1750.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-02T09:00:00Z",
      updated_at: "2026-10-02T09:00:00Z",
    });

    await ordersService.create({
      customer_id: "c1",
      date: "2026-10-02",
      margin_pct: "175",
      items: [{ product_id: "p1", qty: 1, portions: null, note: "" }],
    });
    expect(JSON.parse(lastCall(fetchMock).init.body as string).margin_pct).toBe("175");
  });
});

describe("ordersService — PATCH", () => {
  it("update manda solo los campos presentes (PATCH parcial)", async () => {
    const fetchMock = mockFetch(200, {
      id: "o1",
      customer: { id: "c1", name: "María", phone: "11" },
      date: "2026-10-03",
      status: "nuevo",
      margin_pct: null,
      items: [],
      total: "0.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-01T12:00:00Z",
      updated_at: "2026-10-03T09:00:00Z",
    });

    await ordersService.update("o1", {
      date: "2026-10-03",
      items: [{ product_id: "p2", qty: 3, portions: null, note: "" }],
    });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/orders/o1`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      date: "2026-10-03",
      items: [{ product_id: "p2", qty: 3, note: "" }],
    });
  });

  it("changeStatus manda el nuevo estado a /status", async () => {
    const fetchMock = mockFetch(200, {
      id: "o1",
      customer: { id: "c1", name: "María", phone: "11" },
      date: "2026-10-01",
      status: "confirmado",
      margin_pct: null,
      items: [],
      total: "0.00",
      whatsapp_sent_at: null,
      created_at: "2026-10-01T12:00:00Z",
      updated_at: "2026-10-01T12:30:00Z",
    });

    await ordersService.changeStatus("o1", "confirmado");
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/orders/o1/status`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ status: "confirmado" });
  });
});

describe("ordersService — preview y whatsapp", () => {
  it("preview manda items y margen, convierte centavos", async () => {
    const fetchMock = mockFetch(200, {
      margin_pct: "100",
      tenant_margin_pct: "100",
      items: [
        {
          product_id: "p1",
          product_name: "Torta de Limón",
          qty: 2,
          portions: 6,
          complete: true,
          missing_ingredients: [],
          price: {
            materials: "700.00",
            waste: "50.00",
            materials_con_merma: "750.00",
            labor: "55.00",
            gas: "0.00",
            base: "775.00",
            margin_pct: "100",
            final: "1550.00",
            rounded: "1550",
          },
          lines: [],
          rounded: "3100",
        },
      ],
      total: "3100.00",
    });

    const res = await ordersService.preview(
      [{ product_id: "p1", qty: 2, portions: null, note: "" }],
      null,
    );

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/orders/preview`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      margin_pct: null,
      items: [{ product_id: "p1", qty: 2, note: "" }],
    });
    expect(res.margin_pct).toBe(100);
    expect(res.tenant_margin_pct).toBe(100);
    expect(res.total).toBe(310000);
    expect(res.items[0].price.base).toBe(77500);
  });

  it("whatsapp hace POST a /whatsapp y devuelve url+message", async () => {
    const fetchMock = mockFetch(200, {
      url: "https://wa.me/5491122334455?text=hola",
      message: "Hola María, tu pedido...",
    });

    const res = await ordersService.whatsapp("o1");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/orders/o1/whatsapp`);
    expect(res.url).toContain("wa.me");
  });
});

describe("customersService", () => {
  it("list arma el query con q, page y page_size", async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0, page: 1, page_size: 50 });

    await customersService.list("maria", 1, 50);
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/customers?q=maria&page=1&page_size=50`,
    );

    await customersService.list(undefined, 2, 20);
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/customers?page=2&page_size=20`);
  });

  it("create: 201 devuelve el cliente creado", async () => {
    const fetchMock = mockFetch(201, {
      id: "c2",
      name: "Nueva",
      phone: "22",
      created_at: "2026-10-01T12:00:00Z",
    });

    const created = await customersService.create({ name: "Nueva", phone: "22" });
    expect(created.id).toBe("c2");
    expect(JSON.parse(lastCall(fetchMock).init.body as string)).toEqual({
      name: "Nueva",
      phone: "22",
    });
  });

  it("create: 409 (dedupe) adopta el cliente existente sin lanzar", async () => {
    const fetchMock = mockFetch(409, {
      existing: {
        id: "c1",
        name: "María",
        phone: "11",
        created_at: "2026-09-01T12:00:00Z",
      },
    });

    const adopted = await customersService.create({ name: "María", phone: "11" });
    expect(adopted.id).toBe("c1");
  });

  it("create: 409 sin payload utilizable vuelve a lanzar", async () => {
    mockFetch(409, null);

    await expect(
      customersService.create({ name: "X", phone: "1" }),
    ).rejects.toThrow();
  });
});

describe("insufficientStockOf", () => {
  it("extrae el 409 de stock insuficiente y convierte a centavos", async () => {
    const fetchMock = mockFetch(409, {
      insufficient_stock: [
        {
          ingredient_id: "i1",
          ingredient_name: "Harina 000",
          available: "1.50",
          required: "2.25",
        },
      ],
    });

    let caught: unknown;
    try {
      await ordersService.changeStatus("o1", "confirmado");
    } catch (e) {
      caught = e;
    }

    const stock = insufficientStockOf(caught);
    expect(stock).not.toBeNull();
    expect(stock?.insufficient_stock[0]).toEqual({
      ingredient_id: "i1",
      ingredient_name: "Harina 000",
      available: 150,
      required: 225,
    });
  });

  it("devuelve null para errores distintos de stock", async () => {
    mockFetch(500, { detail: "boom" });

    let caught: unknown;
    try {
      await ordersService.changeStatus("o1", "confirmado");
    } catch (e) {
      caught = e;
    }

    expect(insufficientStockOf(caught)).toBeNull();
  });
});

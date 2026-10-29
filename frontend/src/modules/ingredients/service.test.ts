import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { ingredientsService } from "./service";

/**
 * Tests del service de ingredientes: verifican el contrato HTTP (path, método,
 * body) y el manejo de las respuestas especiales (204 en DELETE, 409 con
 * impacto). Se mockea fetch — nada de red.
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

describe("ingredientsService — GET", () => {
  it("list arma el querystring solo con los filtros presentes", async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0, page: 1, page_size: 50 });

    await ingredientsService.list({ q: "harina", page: 2, page_size: 50 });
    let call = lastCall(fetchMock);
    expect(call.url).toBe(`${API_BASE}/ingredients?q=harina&page=2&page_size=50`);

    await ingredientsService.list();
    call = lastCall(fetchMock);
    expect(call.url).toBe(`${API_BASE}/ingredients`);
  });

  it("getDetail pide los movimientos cuando se los pide", async () => {
    const fetchMock = mockFetch(200, { ingredient: {}, movements: [] });

    await ingredientsService.getDetail("abc", true);
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/ingredients/abc?include_movements=true`);

    await ingredientsService.getDetail("abc", false);
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/ingredients/abc?include_movements=false`);
  });

  it("listMovements pagina el historial", async () => {
    const fetchMock = mockFetch(200, { items: [], total: 0, page: 1, page_size: 50 });

    await ingredientsService.listMovements("abc", 3);
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/ingredients/abc/movements?page=3&page_size=50`,
    );
  });
});

describe("ingredientsService — escrituras", () => {
  it("create hace POST con el body serializado", async () => {
    const fetchMock = mockFetch(201, { id: "1" });
    const payload = {
      name: "Harina",
      unit: "kg" as const,
      price_per_unit: 1200,
      stock_qty: 5,
      low_stock_threshold: 1,
    };

    await ingredientsService.create(payload);

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/ingredients`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(payload);
  });

  it("update hace PATCH al recurso", async () => {
    const fetchMock = mockFetch(200, { id: "1" });

    await ingredientsService.update("1", { price_per_unit: 900 });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/ingredients/1`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ price_per_unit: 900 });
  });

  it("adjustStock hace POST al sub-recurso stock", async () => {
    const fetchMock = mockFetch(200, { stock_qty: "7", movement: {} });

    await ingredientsService.adjustStock("1", { delta: 2, reason: "compra", ref: "Factura A" });

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/ingredients/1/stock`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      delta: 2,
      reason: "compra",
      ref: "Factura A",
    });
  });

  it("importLines envía las líneas como array", async () => {
    const fetchMock = mockFetch(201, { created: 2, errors: [] });

    await ingredientsService.importLines(["Harina;kg;1200", "Leche;L;150"]);

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/ingredients/import`);
    expect(JSON.parse(init.body as string)).toEqual({
      lines: ["Harina;kg;1200", "Leche;L;150"],
    });
  });
});

describe("ingredientsService — casos especiales del contrato", () => {
  it("remove resuelve sin cuerpo en un 204", async () => {
    const fetchMock = mockFetch(204, undefined);

    await expect(ingredientsService.remove("1")).resolves.toBeUndefined();

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/ingredients/1`);
    expect(init.method).toBe("DELETE");
  });

  it("remove expone el 409 con el impacto en recetas (UC-05)", async () => {
    mockFetch(409, { impacted_recipes: 3 });

    const error = await ingredientsService.remove("1").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).payload).toEqual({ impacted_recipes: 3 });
  });

  it("un 422 devuelve el detalle del backend en el mensaje", async () => {
    mockFetch(422, { detail: "Stock insuficiente" });

    const error = await ingredientsService.create({
      name: "Harina",
      unit: "kg",
      price_per_unit: 1,
      stock_qty: 0,
      low_stock_threshold: 0,
    }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(422);
    expect((error as ApiError).message).toBe("Stock insuficiente");
  });
});

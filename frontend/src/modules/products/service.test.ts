import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { productsService } from "./service";

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

describe("productsService — GET", () => {
  it("list arma el querystring solo con los filtros presentes", async () => {
    const fetchMock = mockFetch(200, {
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      categories: [],
    });

    await productsService.list({
      q: "torta",
      category: "Tortas",
      page: 2,
      page_size: 20,
    });
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/products?q=torta&category=Tortas&page=2&page_size=20`,
    );

    await productsService.list();
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/products`);
  });

  it("getDetail pide el producto por id", async () => {
    const fetchMock = mockFetch(200, { id: "abc" });

    await productsService.getDetail("abc");
    expect(lastCall(fetchMock).url).toBe(`${API_BASE}/products/abc`);
  });
});

describe("productsService — escrituras", () => {
  it("create hace POST con el payload (qty y precio como number)", async () => {
    const fetchMock = mockFetch(201, { id: "nuevo" });
    const payload = {
      name: "Torta",
      category: "Tortas",
      description: "",
      prep_time_min: 60,
      servings: 8,
      difficulty: "simple" as const,
      recipe: [{ ingredient_id: "harina", qty: 250, unit: "g" as const }],
    };

    await productsService.create(payload);
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/products`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(payload);
  });

  it("update hace PATCH al id", async () => {
    const fetchMock = mockFetch(200, { id: "abc" });

    await productsService.update("abc", { servings: 10 });
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/products/abc`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ servings: 10 });
  });
});

describe("productsService — DELETE (RF-P4-08)", () => {
  it("204 sin pedidos históricos → null", async () => {
    const fetchMock = mockFetch(204, undefined);

    const result = await productsService.remove("abc");
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/products/abc`);
    expect(init.method).toBe("DELETE");
    expect(result).toBeNull();
  });

  it("200 con pedidos históricos → impacted_orders (no bloquea)", async () => {
    mockFetch(200, { impacted_orders: 4 });

    const result = await productsService.remove("abc");
    expect(result).toEqual({ impacted_orders: 4 });
  });
});

describe("productsService — imagen (P12)", () => {
  it("uploadImage manda multipart FormData sin Content-Type JSON", async () => {
    const fetchMock = mockFetch(201, { image_url: "/media/products/abc.jpg" });
    const file = new File([new Uint8Array([1, 2, 3])], "foto.jpg", {
      type: "image/jpeg",
    });

    const result = await productsService.uploadImage("abc", file);
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/products/abc/image`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBe(file);
    expect(
      (init.headers as Record<string, string> | undefined)?.["Content-Type"],
    ).toBeUndefined();
    expect(result).toEqual({ image_url: "/media/products/abc.jpg" });
  });

  it("removeImage hace DELETE y acepta el 204", async () => {
    const fetchMock = mockFetch(204, undefined);

    await productsService.removeImage("abc");
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/products/abc/image`);
    expect(init.method).toBe("DELETE");
  });

  it("update envía el switch available", async () => {
    const fetchMock = mockFetch(200, { id: "abc" });

    await productsService.update("abc", { available: true });
    const { init } = lastCall(fetchMock);
    expect(JSON.parse(String(init.body))).toEqual({ available: true });
  });
});

describe("productsService — preview de costos (RF-P4-04)", () => {
  it("preview usa el contrato de /pricing/preview", async () => {
    const fetchMock = mockFetch(200, { rounded: 155000 });

    await productsService.preview(
      [
        {
          qty: 250,
          unit: "g",
          price_per_purchase_unit: 280000,
          purchase_unit: "kg",
        },
      ],
      60,
    );
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/pricing/preview`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      line_items: [
        {
          qty: 250,
          unit: "g",
          price_per_purchase_unit: 280000,
          purchase_unit: "kg",
        },
      ],
      prep_minutes: 60,
    });
  });
});

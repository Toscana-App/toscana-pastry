/**
 * Tests del service de configuración: ventana de pedidos (corte de
 * pedidos, RF-P5-07 / RF-P6-09).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { orderWindowService } from "./service";

const API_BASE = "http://localhost:8000/api/v1";

type FetchCall = { url: string; init?: RequestInit };
const lastCall: FetchCall = { url: "" };

function mockFetch(status = 200, body: unknown = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      lastCall.url = String(input);
      lastCall.init = init;
      return new Response(JSON.stringify(body), { status });
    })
  );
}

describe("orderWindowService.get (RF-P6-09)", () => {
  beforeEach(() => {
    lastCall.url = "";
    lastCall.init = undefined;
  });
  afterEach(() => vi.unstubAllGlobals());

  it("lee GET /tenant/order-window", async () => {
    mockFetch(200, { open: true, reopens_at: null, message: "" });
    const window = await orderWindowService.get();
    expect(lastCall.url).toBe(`${API_BASE}/tenant/order-window`);
    expect(window.open).toBe(true);
    expect(window.reopens_at).toBeNull();
    expect(window.message).toBe("");
  });

  it("propaga el 404 del endpoint (sección deshabilitada)", async () => {
    mockFetch(404, { detail: "Not Found" });
    await expect(orderWindowService.get()).rejects.toMatchObject({ status: 404 });
  });
});

describe("orderWindowService.update (RF-P5-07)", () => {
  beforeEach(() => {
    lastCall.url = "";
    lastCall.init = undefined;
  });
  afterEach(() => vi.unstubAllGlobals());

  it("envía PATCH con estado, reapertura y mensaje", async () => {
    mockFetch(200, {
      open: false,
      reopens_at: "2026-11-08T20:00:00",
      message: "Cerrado por mantenimiento",
    });
    const window = await orderWindowService.update({
      open: false,
      reopens_at: "2026-11-08T20:00:00",
      message: "Cerrado por mantenimiento",
    });
    expect(lastCall.url).toBe(`${API_BASE}/tenant/order-window`);
    expect(lastCall.init?.method).toBe("PATCH");
    expect(JSON.parse(String(lastCall.init?.body))).toEqual({
      open: false,
      reopens_at: "2026-11-08T20:00:00",
      message: "Cerrado por mantenimiento",
    });
    expect(window.open).toBe(false);
    expect(window.reopens_at).toBe("2026-11-08T20:00:00");
  });

  it("al abrir envía reopens_at en null", async () => {
    mockFetch(200, { open: true, reopens_at: null, message: "" });
    await orderWindowService.update({ open: true, reopens_at: null, message: "" });
    expect(JSON.parse(String(lastCall.init?.body))).toEqual({
      open: true,
      reopens_at: null,
      message: "",
    });
  });
});

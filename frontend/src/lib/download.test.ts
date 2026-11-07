import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { downloadEndpoint } from "./download";

/**
 * Tests del helper compartido de descargas binarias (Fase 5, UC-08):
 * fetch→blob→download con token en header y filename desde
 * Content-Disposition. Se mockea fetch y el DOM (jsdom no implementa
 * URL.createObjectURL ni navegación de anchors).
 */
const API_BASE = "http://localhost:8000/api/v1";

function mockBlobFetch(
  status: number,
  opts: { body?: unknown; headers?: Record<string, string> } = {},
) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(opts.headers ?? {}),
    json: async () => opts.body ?? null,
    blob: async () => new Blob(["%PDF-1.4 fake"], { type: "application/pdf" }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

let anchor: HTMLAnchorElement | null = null;

beforeEach(() => {
  document.cookie = "auth_token=tok123; path=/";
  anchor = null;
  // jsdom no implementa object URLs ni click de anchors.
  URL.createObjectURL = vi.fn().mockReturnValue("blob:mock");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    // Cast: `anchor = this` dispara no-this-alias; la aserción no cambia el tipo.
    anchor = this as HTMLAnchorElement;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("downloadEndpoint", () => {
  it("llama al endpoint con el token de acceso en el header", async () => {
    const fetchMock = mockBlobFetch(200);

    await downloadEndpoint("/orders/export?format=pdf", "pedidos.pdf");

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/orders/export?format=pdf`,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer tok123" }),
      }),
    );
  });

  it("descarga con el filename de Content-Disposition", async () => {
    mockBlobFetch(200, {
      headers: {
        "Content-Disposition":
          'attachment; filename="resumen_semanal_2026-W45.pdf"',
      },
    });

    await downloadEndpoint("/orders/weekly/pdf?week=2026-W45", "fallback.pdf");

    expect(anchor?.download).toBe("resumen_semanal_2026-W45.pdf");
    expect(anchor?.href).toBe("blob:mock");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock");
  });

  it("usa el filename de respaldo cuando no hay Content-Disposition", async () => {
    mockBlobFetch(200);

    await downloadEndpoint("/budgets/export?format=csv", "presupuestos.csv");

    expect(anchor?.download).toBe("presupuestos.csv");
  });

  it("lanza con el mensaje del backend cuando la respuesta no es OK", async () => {
    mockBlobFetch(400, { body: { detail: "Sección de pedidos cerrada" } });

    await expect(downloadEndpoint("/orders/export", "pedidos.csv")).rejects.toThrow(
      "Sección de pedidos cerrada",
    );
  });

  it("lanza con un mensaje genérico cuando el cuerpo no es JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({}),
      json: async () => {
        throw new Error("no es JSON");
      },
      blob: async () => new Blob([]),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(downloadEndpoint("/orders/export", "pedidos.csv")).rejects.toThrow();
  });
});

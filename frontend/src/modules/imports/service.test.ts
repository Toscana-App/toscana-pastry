import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { importsService } from "./service";

/**
 * Tests del service de importación CSV (T-CSV-8): contrato HTTP de los 5
 * endpoints + el upload multipart (FormData) + la plantilla como texto.
 * Se mockea fetch — nada de red.
 */
const API_BASE = "http://localhost:8000/api/v1";

function mockFetch(status: number, body: unknown, text?: string) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => text ?? (body == null ? "" : JSON.stringify(body)),
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

describe("importsService — plantilla", () => {
  it("template hace GET al endpoint de plantilla con la entidad", async () => {
    const fetchMock = mockFetch(200, null, "nombre;unidad;precio_por_unidad\n");

    const csv = await importsService.template("ingredients");

    expect(csv).toBe("nombre;unidad;precio_por_unidad\n");
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/imports/template?entity=ingredients`);
    expect(init.method).toBeUndefined();
  });

  it("template expone un 404 como ApiError", async () => {
    mockFetch(404, { detail: "Entidad desconocida" });

    const err = await importsService.template("bogus" as never).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
  });
});

describe("importsService — upload multipart", () => {
  it("upload envía el archivo y la entidad en un FormData (sin Content-Type JSON)", async () => {
    const fetchMock = mockFetch(201, {
      import_id: "imp1",
      total_rows: 2,
      valid_rows: 2,
      invalid_rows: 0,
    });
    const file = new File(["a;b\n1;2"], "insumos.csv", { type: "text/csv" });

    await importsService.upload(file, "ingredients");

    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/imports`);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get("entity")).toBe("ingredients");
    expect(fd.get("file")).toBeInstanceOf(File);
    // Multipart: NO se setea Content-Type application/json.
    expect(init.headers).not.toHaveProperty("Content-Type");
  });

  it("upload expone el 413 (archivo demasiado grande)", async () => {
    mockFetch(413, { detail: "Archivo demasiado grande (máx. 5 MB)" });
    const file = new File(["x"], "big.csv", { type: "text/csv" });

    const err = await importsService.upload(file, "ingredients").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(413);
  });
});

describe("importsService — rows / confirm / discard", () => {
  it("rows arma el querystring de paginación y filtro", async () => {
    const fetchMock = mockFetch(200, {
      import_id: "imp1",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      rows: [],
      page: 1,
      page_size: 50,
    });

    await importsService.rows("imp1", 2, 50, "invalid");
    expect(lastCall(fetchMock).url).toBe(
      `${API_BASE}/imports/imp1/rows?page=2&page_size=50&status=invalid`,
    );
  });

  it("confirm hace POST al sub-recurso confirm", async () => {
    const fetchMock = mockFetch(200, { created: 2, skipped: 0, errors: [] });

    await importsService.confirm("imp1");
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/imports/imp1/confirm`);
    expect(init.method).toBe("POST");
  });

  it("discard hace DELETE al recurso (204)", async () => {
    const fetchMock = mockFetch(204, undefined);

    await expect(importsService.discard("imp1")).resolves.toBeUndefined();
    const { url, init } = lastCall(fetchMock);
    expect(url).toBe(`${API_BASE}/imports/imp1`);
    expect(init.method).toBe("DELETE");
  });

  it("discard expone un 409 (ya confirmada)", async () => {
    mockFetch(409, { detail: "Ya confirmada" });

    const err = await importsService.discard("imp1").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(409);
  });
});

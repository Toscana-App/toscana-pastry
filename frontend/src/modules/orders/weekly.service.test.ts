import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { weeklyService } from "./weekly.service";
import { downloadEndpoint } from "@/lib/download";

vi.mock("@/lib/download", () => ({
  downloadEndpoint: vi.fn().mockResolvedValue(undefined),
}));

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
  const [url] = fetchMock.mock.calls.at(-1) as [string];
  return url;
}

beforeEach(() => {
  document.cookie = "auth_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  vi.mocked(downloadEndpoint).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("weeklyService — GET /orders/weekly", () => {
  it("get() pide la semana actual y mapea centavos tal cual", async () => {
    const fetchMock = mockFetch(200, {
      week: { from: "2026-11-02", to: "2026-11-08" },
      items: [
        {
          id: "o1",
          customer: "María",
          date: "2026-11-03",
          items_count: 2,
          total: 310000,
          paid: true,
          payment_method: "cash",
        },
      ],
      totals: { amount: 465000, paid: 310000, unpaid: 155000 },
    });

    const res = await weeklyService.get();

    expect(lastCall(fetchMock)).toBe(`${API_BASE}/orders/weekly`);
    expect(res.week.from).toBe("2026-11-02");
    expect(res.week.to).toBe("2026-11-08");
    expect(res.items[0].customer).toBe("María");
    expect(res.items[0].total).toBe(310000);
    expect(res.items[0].paid).toBe(true);
    expect(res.totals.amount).toBe(465000);
    expect(res.totals.unpaid).toBe(155000);
  });

  it("get(week) pasa la semana ISO en el querystring", async () => {
    const fetchMock = mockFetch(200, {
      week: { from: "2026-11-02", to: "2026-11-08" },
      items: [],
      totals: { amount: 0, paid: 0, unpaid: 0 },
    });

    await weeklyService.get("2026-W45");

    expect(lastCall(fetchMock)).toBe(`${API_BASE}/orders/weekly?week=2026-W45`);
  });
});

describe("weeklyService — exports", () => {
  it("exportCsv descarga /orders/export con el rango de la semana", async () => {
    await weeklyService.exportCsv({ from: "2026-11-02", to: "2026-11-08" });

    expect(downloadEndpoint).toHaveBeenCalledWith(
      "/orders/export?from=2026-11-02&to=2026-11-08&format=csv",
      "pedidos_semana.csv",
    );
  });

  it("exportPdf(week) descarga /orders/weekly/pdf?week=…", async () => {
    await weeklyService.exportPdf("2026-W45");

    expect(downloadEndpoint).toHaveBeenCalledWith(
      "/orders/weekly/pdf?week=2026-W45",
      "resumen_semanal_2026-W45.pdf",
    );
  });

  it("exportPdf() sin week exporta la semana actual", async () => {
    await weeklyService.exportPdf();

    expect(downloadEndpoint).toHaveBeenCalledWith(
      "/orders/weekly/pdf",
      "resumen_semanal.pdf",
    );
  });
});

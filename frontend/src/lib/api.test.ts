import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, AUTH_SESSION_CLEARED_EVENT } from "./api";

const API_BASE = "http://localhost:8000/api/v1";

function jsonResponse(status: number, body: unknown = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch session handling", () => {
  it("sends the HttpOnly session cookies and no Authorization header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { ok: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/auth/me");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(init.headers).not.toHaveProperty("Authorization");
  });

  it("on 401 refreshes the session once and retries the request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401))
      .mockResolvedValueOnce(jsonResponse(204))
      .mockResolvedValueOnce(jsonResponse(200, { email: "a@b.c" }));
    vi.stubGlobal("fetch", fetchMock);

    const data = await apiFetch<{ email: string }>("/auth/me");

    expect(data.email).toBe("a@b.c");
    expect(fetchMock.mock.calls[1]).toEqual([
      `${API_BASE}/auth/refresh`,
      { method: "POST", credentials: "include" },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("concurrent 401s share a single refresh call", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.endsWith("/auth/refresh") ? jsonResponse(204) : jsonResponse(401),
    );
    vi.stubGlobal("fetch", fetchMock);

    await Promise.allSettled([apiFetch("/a"), apiFetch("/b")]);

    const refreshCalls = fetchMock.mock.calls.filter(([url]) =>
      url.endsWith("/auth/refresh"),
    );
    expect(refreshCalls).toHaveLength(1);
  });

  it("clears the session when the refresh fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401))
      .mockResolvedValueOnce(jsonResponse(401));
    vi.stubGlobal("fetch", fetchMock);
    const onCleared = vi.fn();
    window.addEventListener(AUTH_SESSION_CLEARED_EVENT, onCleared);

    await expect(apiFetch("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(onCleared).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_SESSION_CLEARED_EVENT, onCleared);
  });
});

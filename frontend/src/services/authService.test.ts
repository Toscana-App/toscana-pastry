import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

const apiFetchMock = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiFetch: (...args: unknown[]) => apiFetchMock(...args),
    clearSession: vi.fn(),
  };
});

import { authService } from "./authService";

beforeEach(() => {
  apiFetchMock.mockReset();
});

describe("authService", () => {
  it("fetchGoogleNonce does GET /auth/google/nonce without session refresh", async () => {
    apiFetchMock.mockResolvedValue({ nonce: "abc123" });

    const data = await authService.fetchGoogleNonce();

    expect(apiFetchMock).toHaveBeenCalledTimes(1);
    const [endpoint, options, allowRefresh] = apiFetchMock.mock.calls[0] as [
      string,
      unknown,
      boolean,
    ];
    expect(endpoint).toBe("/auth/google/nonce");
    expect(options).toBeUndefined();
    expect(allowRefresh).toBe(false);
    expect(data).toEqual({ nonce: "abc123" });
  });

  it("loginWithGoogleCredential POSTs the credential and disables session refresh", async () => {
    apiFetchMock.mockResolvedValue({
      user_id: "u1",
      email: "u@gmail.com",
      role: "customer",
      state: "signed_in",
    });

    const data = await authService.loginWithGoogleCredential("jwt.token");

    const [endpoint, options, allowRefresh] = apiFetchMock.mock.calls[0] as [
      string,
      RequestInit,
      boolean,
    ];
    expect(endpoint).toBe("/auth/google/signin");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      credential: "jwt.token",
    });
    expect(allowRefresh).toBe(false);
    expect(data.state).toBe("signed_in");
  });

  it("exposes the 409 detail.state (no_account / link_pending) for branching", async () => {
    for (const state of ["no_account", "link_pending"] as const) {
      apiFetchMock.mockReset();
      apiFetchMock.mockRejectedValue(
        new ApiError(409, "conflict", {
          detail: { message: `msg-${state}`, state },
        }),
      );

      let caught: unknown;
      try {
        await authService.loginWithGoogleCredential("jwt.token");
      } catch (error) {
        caught = error;
      }

      expect(caught).toBeInstanceOf(ApiError);
      const error = caught as ApiError;
      expect(error.status).toBe(409);
      const detail = (
        error.payload as { detail?: { message: string; state: string } }
      ).detail;
      expect(detail?.state).toBe(state);
      expect(detail?.message).toBe(`msg-${state}`);
    }
  });
});

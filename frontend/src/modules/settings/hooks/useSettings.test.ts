import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { settingsService } from "../service";
import { SETTINGS_DEFAULTS } from "../types";
import { useSettings } from "./useSettings";

vi.mock("../service", () => ({
  settingsService: { get: vi.fn(), update: vi.fn() },
}));

const service = vi.mocked(settingsService);

beforeEach(() => {
  vi.resetAllMocks();
});

describe("useSettings field errors", () => {
  it("maps the 422 loc to the matching form field", async () => {
    service.get.mockRejectedValue(new Error("skip"));
    const { result } = renderHook(() => useSettings());
    await waitFor(() => expect(result.current.loading).toBe(false));

    service.update.mockRejectedValue(
      new ApiError(422, "invalid", {
        detail: [
          { loc: ["body", "margin_pct"], msg: "Must be at most 100" },
          { loc: ["body", "unknown_field"], msg: "ignored" },
        ],
      }),
    );

    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.save(SETTINGS_DEFAULTS);
    });

    expect(ok).toBe(false);
    expect(result.current.fieldErrors).toEqual({ margin_pct: "Must be at most 100" });
  });
});

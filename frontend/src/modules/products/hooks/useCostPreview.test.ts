import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { Ingredient } from "@/modules/ingredients/types";
import { productsService } from "../service";
import type { PriceBreakdown } from "../types";
import { useCostPreview } from "./useCostPreview";

vi.mock("../service", () => ({ productsService: { preview: vi.fn() } }));

const preview = vi.mocked(productsService.preview);
const flour: Ingredient = {
  id: "i1",
  name: "Harina",
  unit: "kg",
  price_per_unit: 1000,
  stock_qty: "1",
  low_stock_threshold: "0",
  status: "OK",
};
const byId = new Map([[flour.id, flour]]);
const recipe = [{ ingredient_id: "i1", qty: 200, unit: "g" as const }];
const breakdown = { final: 10 } as unknown as PriceBreakdown;

beforeEach(() => {
  vi.useFakeTimers();
  preview.mockReset();
});

describe("useCostPreview", () => {
  it("does not call the backend without valid lines", () => {
    const { result } = renderHook(() =>
      useCostPreview([{ ingredient_id: "i1", qty: 0, unit: "g" }], 30, byId),
    );
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(preview).not.toHaveBeenCalled();
    expect(result.current).toEqual({ breakdown: null, error: null, loading: false });
  });

  it("debounces 300 ms, sends lines + clamped prep time and exposes the breakdown", async () => {
    preview.mockResolvedValue(breakdown);
    const { result } = renderHook(() => useCostPreview(recipe, 5000, byId));

    expect(result.current.loading).toBe(true);
    await act(async () => {
      vi.advanceTimersByTime(299);
    });
    expect(preview).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(preview).toHaveBeenCalledWith(
      [{ qty: 200, unit: "g", price_per_purchase_unit: 1000, purchase_unit: "kg" }],
      1440,
    );
    expect(result.current).toEqual({ breakdown, error: null, loading: false });
  });

  it("exposes the error message when the preview fails", async () => {
    preview.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useCostPreview(recipe, 30, byId));

    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toEqual({ breakdown: null, error: "boom", loading: false });
  });
});

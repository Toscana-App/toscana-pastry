import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { ingredientsService } from "../service";
import type { Ingredient, StockMovement } from "../types";
import { useIngredientDetail } from "./useIngredientDetail";

vi.mock("../service", () => ({
  ingredientsService: {
    getDetail: vi.fn(),
    adjustStock: vi.fn(),
    remove: vi.fn(),
  },
}));

const service = vi.mocked(ingredientsService);

const ingredient: Ingredient = {
  id: "1",
  name: "Flour",
  unit: "kg",
  price_per_unit: 100,
  stock_qty: "10",
  low_stock_threshold: "3",
  status: "OK",
};

const movement: StockMovement = {
  id: "m1",
  qty_delta: "-2",
  reason: "manual",
  ref: null,
  created_at: "2026-01-01T00:00:00Z",
};

async function setup() {
  service.getDetail.mockResolvedValue({ ingredient, movements: [] });
  const hook = renderHook(() => useIngredientDetail("1"));
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  return hook;
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("useIngredientDetail", () => {
  it("a successful adjustment updates stock and prepends the movement", async () => {
    const { result } = await setup();
    service.adjustStock.mockResolvedValue({ stock_qty: "8", movement });

    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.adjustStock(-2, "manual" as never);
    });

    expect(outcome).toEqual({ ok: true });
    expect(result.current.ingredient?.stock_qty).toBe("8");
    expect(result.current.movements[0]).toEqual(movement);
  });

  it("a 400 rolls back stock_qty and status and returns the message", async () => {
    const { result } = await setup();
    service.adjustStock.mockRejectedValue(new ApiError(400, "Insufficient stock", null));

    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.adjustStock(-10, "manual" as never);
    });

    expect(outcome).toEqual({ ok: false, message: "Insufficient stock" });
    expect(result.current.ingredient?.stock_qty).toBe("10");
    expect(result.current.ingredient?.status).toBe("OK");
  });

  it("remove returns the impact on a 409", async () => {
    const { result } = await setup();
    service.remove.mockRejectedValue(
      new ApiError(409, "In use", { impacted_recipes: 3 }),
    );

    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.remove();
    });

    expect(outcome).toEqual({ impacted_recipes: 3 });
  });
});

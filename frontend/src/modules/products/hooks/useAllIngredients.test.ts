import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { ingredientsService } from "@/modules/ingredients/service";
import type { Ingredient } from "@/modules/ingredients/types";
import { useAllIngredients } from "./useAllIngredients";

vi.mock("@/modules/ingredients/service", () => ({
  ingredientsService: { list: vi.fn() },
}));

const list = vi.mocked(ingredientsService.list);
const make = (id: string) => ({ id, name: id }) as unknown as Ingredient;

beforeEach(() => {
  list.mockReset();
});

describe("useAllIngredients", () => {
  it("walks every page until the total is reached", async () => {
    list
      .mockResolvedValueOnce({ items: [make("a"), make("b")], total: 3, page: 1, page_size: 100 })
      .mockResolvedValueOnce({ items: [make("c")], total: 3, page: 2, page_size: 100 });
    const { result } = renderHook(() => useAllIngredients());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.ingredients.map((i) => i.id)).toEqual(["a", "b", "c"]);
    expect(list).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeNull();
  });

  it("reports an error when the catalog cannot be loaded", async () => {
    list.mockImplementation(() => Promise.reject(new Error("x")));
    const { result } = renderHook(() => useAllIngredients());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("No se pudieron cargar los insumos del catálogo.");
  });
});

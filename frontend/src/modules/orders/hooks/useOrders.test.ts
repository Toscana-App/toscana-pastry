import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/modules/shared/useDebounce", () => ({ useDebounce: <T,>(v: T) => v }));
vi.mock("../service", () => ({ ordersService: { list: vi.fn() } }));

import { ordersService } from "../service";
import { useOrders } from "./useOrders";

const listMock = vi.mocked(ordersService.list);

beforeEach(() => {
  listMock.mockReset();
  listMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 } as never);
});

describe("useOrders — loading no queda colgado", () => {
  it("termina de cargar al inicio", async () => {
    const { result } = renderHook(() => useOrders());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("setStatus con el mismo valor no deja loading en true", async () => {
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setStatus(null));
    expect(result.current.loading).toBe(false);
  });

  it("búsqueda con espacio final (mismo término) no deja loading en true", async () => {
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setQuery("   "));
    expect(result.current.loading).toBe(false);
  });

  it("ir a la página actual no deja loading en true", async () => {
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.goToPage(1));
    expect(result.current.loading).toBe(false);
  });

  it("un filtro nuevo vuelve a cargar y termina", async () => {
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setStatus("nuevo" as never));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    const listCalls = listMock.mock.calls
      .map((call) => call[0] as unknown as { page_size: number; status?: string })
      .filter((params) => params.page_size === 20);
    expect(listCalls).toHaveLength(2);
    expect(listCalls.at(-1)?.status).toBe("nuevo");
  });

  it("reload vuelve a pedir y termina", async () => {
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.reload());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
  });
});

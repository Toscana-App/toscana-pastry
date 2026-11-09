import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: { role: "staff" } }) }));
vi.mock("@/modules/shared/useDebounce", () => ({ useDebounce: <T,>(v: T) => v }));
vi.mock("@/modules/products/service", () => ({
  productsService: { list: vi.fn() },
}));
vi.mock("../service", () => ({
  customersService: { list: vi.fn(), create: vi.fn() },
  ordersService: { getDetail: vi.fn(), create: vi.fn(), update: vi.fn(), preview: vi.fn() },
  insufficientStockOf: vi.fn(() => null),
}));

import { productsService } from "@/modules/products/service";
import { customersService, ordersService } from "../service";
import { useOrderWizard } from "./useOrderWizard";

const CUSTOMER_ID = "11111111-1111-4111-8111-111111111111";
const PRODUCT_ID = "22222222-2222-4222-8222-222222222222";

beforeEach(() => {
  push.mockReset();
  vi.mocked(productsService.list).mockResolvedValue({ items: [] } as never);
  vi.mocked(customersService.list).mockResolvedValue({ items: [] } as never);
  vi.mocked(ordersService.create).mockReset().mockResolvedValue({ id: "new-1" } as never);
  vi.mocked(ordersService.update).mockReset().mockResolvedValue({} as never);
  vi.mocked(ordersService.getDetail).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useOrderWizard — submit payload", () => {
  it("sends portions null when empty and margin_pct null when empty", async () => {
    const { result } = renderHook(() => useOrderWizard());
    act(() => {
      result.current.setCustomerId(CUSTOMER_ID);
      result.current.updateItem(1, { product_id: PRODUCT_ID, qty: "2" });
    });
    await act(async () => {
      await result.current.submit();
    });
    expect(ordersService.create).toHaveBeenCalledWith({
      customer_id: CUSTOMER_ID,
      date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      margin_pct: null,
      items: [{ product_id: PRODUCT_ID, qty: 2, portions: null, note: "" }],
    });
    expect(push).toHaveBeenCalledWith("/pedidos/new-1");
  });

  it("sends margin_pct as a string and numeric portions when filled", async () => {
    const { result } = renderHook(() => useOrderWizard());
    act(() => {
      result.current.setCustomerId(CUSTOMER_ID);
      result.current.setMargin("35");
      result.current.updateItem(1, { product_id: PRODUCT_ID, portions: "12", note: "sin nueces" });
    });
    await act(async () => {
      await result.current.submit();
    });
    expect(ordersService.create).toHaveBeenCalledWith(
      expect.objectContaining({
        margin_pct: "35",
        items: [{ product_id: PRODUCT_ID, qty: 1, portions: 12, note: "sin nueces" }],
      }),
    );
  });
});

describe("useOrderWizard — edit mode", () => {
  it("injects the order's customer into the options and prefills the form", async () => {
    vi.mocked(ordersService.getDetail).mockResolvedValue({
      customer: { id: CUSTOMER_ID, name: "Ana", phone: "1" },
      date: "2026-01-15",
      margin_pct: null,
      items: [{ product_id: PRODUCT_ID, qty: 3, portions: 8, note: "n" }],
    } as never);
    const { result } = renderHook(() => useOrderWizard("order-9"));
    expect(result.current.loadingDetail).toBe(true);
    await waitFor(() => expect(result.current.loadingDetail).toBe(false));
    expect(result.current.customerOptions).toEqual([{ value: CUSTOMER_ID, label: "Ana" }]);
    expect(result.current.customerId).toBe(CUSTOMER_ID);
    expect(result.current.date).toBe("2026-01-15");
    expect(result.current.margin).toBe("");

    await act(async () => {
      await result.current.submit();
    });
    expect(ordersService.update).toHaveBeenCalledWith(
      "order-9",
      expect.objectContaining({ items: [{ product_id: PRODUCT_ID, qty: 3, portions: 8, note: "n" }] }),
    );
    expect(push).toHaveBeenCalledWith("/pedidos/order-9");
  });
});

describe("useOrderWizard — default date", () => {
  it("uses the local date, not UTC", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 0, 10, 23, 30));
    const { result } = renderHook(() => useOrderWizard());
    expect(result.current.date).toBe("2026-01-10");
  });
});

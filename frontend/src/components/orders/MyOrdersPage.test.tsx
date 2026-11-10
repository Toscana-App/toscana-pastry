import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import MyOrdersPage from "./MyOrdersPage";
import type { OrderDetail } from "@/types/orders";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));
vi.mock("@/services/ordersService", () => ({
  fetchMyOrders: vi.fn(),
  fetchMyOrderByCode: vi.fn(),
  initOrderPayment: vi.fn(),
}));
vi.mock("goey-toast", () => ({
  gooeyToast: { error: vi.fn(), success: vi.fn() },
}));

import {
  fetchMyOrders,
  fetchMyOrderByCode,
} from "@/services/ordersService";

const order: OrderDetail = {
  id: "ord-1",
  code: "TOS-0001",
  status: "nuevo",
  date: "2026-01-10",
  delivery_mode: "delivery",
  delivery_address: "Av. Corrientes 1",
  payment_method: "mercadopago",
  payment_status: null,
  paid: false,
  total: "1000.00",
  coupon_code: null,
  discount_amount: null,
  items: [
    {
      product_id: "p1",
      product_name: "Torta",
      quantity: 1,
      unit_price: "1000.00",
      total: "1000.00",
    },
  ],
} as OrderDetail;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchMyOrders).mockResolvedValue({
    orders: [order],
    total: 1,
  } as never);
  vi.mocked(fetchMyOrderByCode).mockResolvedValue(order);
});

describe("MyOrdersPage", () => {
  it("renders a page heading and the order card", async () => {
    render(<MyOrdersPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Mis pedidos" })
      ).toBeInTheDocument();
      expect(screen.getByText("TOS-0001")).toBeInTheDocument();
    });
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("shows an empty state with a catalog CTA", async () => {
    vi.mocked(fetchMyOrders).mockResolvedValue({
      orders: [],
      total: 0,
    } as never);
    render(<MyOrdersPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: "Todavía no tenés pedidos",
        })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Ver catálogo" })
      ).toBeInTheDocument();
    });
  });

  it("surfaces a toast when loading the order detail fails", async () => {
    const { gooeyToast } = await import("goey-toast");
    vi.mocked(fetchMyOrderByCode).mockRejectedValue(new Error("boom"));
    render(<MyOrdersPage />);
    await waitFor(() => {
      expect(screen.getByText("TOS-0001")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Ver detalle" }));
    await waitFor(() => {
      expect(vi.mocked(gooeyToast.error)).toHaveBeenCalled();
    });
  });
});

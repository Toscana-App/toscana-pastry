import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import MyOrdersPage from "./MyOrdersPage";
import type { OrderDetail } from "@/types/orders";

vi.mock("@/services/ordersService", () => ({
  fetchMyOrders: vi.fn(),
  fetchMyOrderByCode: vi.fn(),
  initOrderPayment: vi.fn(),
}));
vi.mock("goey-toast", () => ({
  gooeyToast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

import { fetchMyOrderByCode, fetchMyOrders } from "@/services/ordersService";

function makeOrder(overrides: Partial<OrderDetail> = {}): OrderDetail {
  return {
    id: "o1",
    code: "PED-001",
    customer_id: "c1",
    status: "confirmado",
    date: "2026-11-01T12:00:00Z",
    payment_method: "cash",
    delivery_mode: "pickup",
    delivery_address: null,
    coupon_code: null,
    discount_amount: null,
    paid: false,
    payment_status: null,
    total: "12345.50",
    items: [
      {
        product_id: "p1",
        product_name: "Torta",
        quantity: 2,
        unit_price: "3000.00",
        portion_note: "",
        total: "6000.00",
      },
    ],
    created_at: "2026-11-01T12:00:00Z",
    ...overrides,
  };
}

const normalize = (text: string | null) =>
  (text ?? "").replace(/\s/g, " ");

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchMyOrders).mockResolvedValue({
    orders: [makeOrder(), makeOrder({ id: "o2", code: "PED-002", status: "entregado" })],
    total: 2,
    page: 1,
    page_size: 10,
  });
  vi.mocked(fetchMyOrderByCode).mockResolvedValue(makeOrder());
});

describe("MyOrdersPage", () => {
  it("renders each order as a card with code, status and formatted total", async () => {
    render(<MyOrdersPage />);

    expect(await screen.findByText("PED-001")).toBeInTheDocument();
    expect(screen.getByText("PED-002")).toBeInTheDocument();
    expect(screen.getByText("Confirmado")).toBeInTheDocument();
    expect(screen.getByText("Entregado")).toBeInTheDocument();
    const totals = screen.getAllByText((_, el) =>
      /\$\s?12\.345,50/.test(normalize(el?.textContent ?? "")) &&
      el?.tagName === "SPAN" &&
      el.children.length === 0
    );
    expect(totals.length).toBeGreaterThan(0);
  });

  it("renders the status with a Chakra Status indicator", async () => {
    const { container } = render(<MyOrdersPage />);
    await screen.findByText("PED-001");
    expect(container.querySelectorAll(".chakra-status__root").length).toBe(2);
    expect(container.querySelectorAll(".chakra-status__indicator").length).toBe(2);
  });

  it("expands the detail and formats item amounts in ARS", async () => {
    render(<MyOrdersPage />);
    await screen.findByText("PED-001");

    const [button] = screen.getAllByRole("button", { name: "Ver detalle" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);

    expect(await screen.findByText(/Torta × 2/)).toBeInTheDocument();
    await waitFor(() => expect(button).toHaveAttribute("aria-expanded", "true"));
    expect(
      screen.getAllByText((_, el) =>
        /\$\s?6\.000,00/.test(normalize(el?.textContent ?? "")) &&
        el?.children.length === 0
      ).length
    ).toBeGreaterThan(0);
  });

  it("shows the error alert", async () => {
    vi.mocked(fetchMyOrders).mockRejectedValue(new Error("boom"));
    render(<MyOrdersPage />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    vi.mocked(fetchMyOrders).mockResolvedValue({ orders: [], total: 0, page: 1, page_size: 10 });
    render(<MyOrdersPage />);
    expect(await screen.findByText("Todavía no tenés pedidos")).toBeInTheDocument();
  });

  it("paginates", async () => {
    vi.mocked(fetchMyOrders).mockResolvedValue({
      orders: [makeOrder()],
      total: 25,
      page: 1,
      page_size: 10,
    });
    render(<MyOrdersPage />);
    await screen.findByText("PED-001");
    fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(fetchMyOrders).toHaveBeenCalledWith(2, 10));
  });
  it("renders a page heading inside a main landmark", async () => {
    render(<MyOrdersPage />);
    await screen.findByRole("heading", { name: "Mis pedidos" });
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("shows the empty state with a catalog CTA", async () => {
    vi.mocked(fetchMyOrders).mockResolvedValue({ orders: [], total: 0, page: 1, page_size: 10 });
    render(<MyOrdersPage />);
    expect(await screen.findByRole("button", { name: "Ver catálogo" })).toBeInTheDocument();
  });

  it("surfaces a toast when loading the order detail fails", async () => {
    const { gooeyToast } = await import("goey-toast");
    vi.mocked(fetchMyOrderByCode).mockRejectedValue(new Error("detail-boom"));
    render(<MyOrdersPage />);
    await screen.findByText("PED-001");
    const [button] = screen.getAllByRole("button", { name: "Ver detalle" });
    fireEvent.click(button);
    await waitFor(() => expect(vi.mocked(gooeyToast.error)).toHaveBeenCalled());
  });

});

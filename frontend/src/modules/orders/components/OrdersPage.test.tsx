import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders as render } from "@/test-utils";
import { useOrders, type UseOrdersResult } from "../hooks/useOrders";
import type { OrderListItem } from "../types";
import { OrdersPage } from "./OrdersPage";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u1", name: "Admin", role: "admin" } }),
}));
vi.mock("../hooks/useOrders", () => ({
  useOrders: vi.fn(),
}));
vi.mock("../service", () => ({
  ordersService: {
    exportReport: vi.fn(),
  },
}));
vi.mock("@/modules/settings/service", () => ({
  orderWindowService: {
    get: vi.fn().mockResolvedValue({ open: true }),
  },
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

function makeItem(overrides: Partial<OrderListItem> = {}): OrderListItem {
  return {
    id: "o1",
    customer_name: "María",
    customer_phone: "1155550000",
    date: "2026-11-01",
    status: "new",
    item_count: 1,
    total: 100000,
    paid: false,
    created_at: "2026-11-01T12:00:00Z",
    payment_method: "cash",
    receipt_uploaded: false,
    receipt_content_type: null,
    receipt_uploaded_at: null,
    receipt_viewed_at: null,
    ...overrides,
  };
}

function renderWithItems(items: OrderListItem[]) {
  const result: UseOrdersResult = {
    items,
    total: items.length,
    unpaidCount: items.filter((i) => !i.paid).length,
    page: 1,
    query: "",
    status: null,
    paid: null,
    dateFrom: "",
    dateTo: "",
    loading: false,
    error: null,
    setQuery: vi.fn(),
    setStatus: vi.fn(),
    setPaid: vi.fn(),
    setDateFrom: vi.fn(),
    setDateTo: vi.fn(),
    goToPage: vi.fn(),
    reload: vi.fn(),
  };
  vi.mocked(useOrders).mockReturnValue(result);
  render(<OrdersPage />);
}

describe("OrdersPage — badge de comprobante de transferencia (S7)", () => {
  it("transfer con comprobante sin ver: badge sólido 'Comprobante nuevo'", () => {
    renderWithItems([
      makeItem({
        payment_method: "transfer",
        receipt_uploaded: true,
        receipt_content_type: "image/jpeg",
        receipt_uploaded_at: "2026-11-25T10:00:00Z",
        receipt_viewed_at: null,
      }),
    ]);
    expect(screen.getByText("Comprobante nuevo")).toBeInTheDocument();
    expect(screen.queryByText("Comprobante pendiente")).not.toBeInTheDocument();
  });

  it("transfer con comprobante ya visto: badge suave 'Comprobante pendiente'", () => {
    renderWithItems([
      makeItem({
        payment_method: "transfer",
        receipt_uploaded: true,
        receipt_uploaded_at: "2026-11-25T10:00:00Z",
        receipt_viewed_at: "2026-11-25T11:00:00Z",
      }),
    ]);
    expect(screen.getByText("Comprobante pendiente")).toBeInTheDocument();
    expect(screen.queryByText("Comprobante nuevo")).not.toBeInTheDocument();
  });

  it("transfer con comprobante y pagado: sin badge de comprobante", () => {
    renderWithItems([
      makeItem({
        payment_method: "transfer",
        receipt_uploaded: true,
        paid: true,
        receipt_viewed_at: "2026-11-25T11:00:00Z",
      }),
    ]);
    expect(screen.queryByText(/Comprobante/)).not.toBeInTheDocument();
  });

  it("cash: sin badge aunque traiga campo de comprobante (regla solo transfer)", () => {
    renderWithItems([
      makeItem({ receipt_uploaded: true, receipt_viewed_at: null }),
    ]);
    expect(screen.queryByText(/Comprobante/)).not.toBeInTheDocument();
  });

  it("sin comprobante: sin badge", () => {
    renderWithItems([makeItem({ payment_method: "transfer" })]);
    expect(screen.queryByText(/Comprobante/)).not.toBeInTheDocument();
  });
});

import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "@/test-utils";
import { ordersService } from "../service";
import type { OrderDetail, OrderStatus } from "../types";
import { OrderDetailPage } from "./OrderDetailPage";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "u1", name: "Admin", role: "admin" } }),
}));
vi.mock("../service", () => ({
  ordersService: {
    getDetail: vi.fn(),
    changeStatus: vi.fn(),
    markPaid: vi.fn(),
    whatsapp: vi.fn(),
  },
}));
vi.mock("@/modules/invoicing/service", () => ({
  invoicesService: { create: vi.fn(), downloadPdf: vi.fn() },
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

function makeOrder(status: OrderStatus): OrderDetail {
  return {
    id: "o1",
    customer: { id: "c1", name: "María", phone: "1155550000" },
    date: "2026-11-01",
    status,
    margin_pct: null,
    items: [],
    total: 100000,
    paid: false,
    whatsapp_sent_at: null,
    created_at: "2026-11-01T12:00:00Z",
    updated_at: "2026-11-01T12:00:00Z",
    invoice: null,
  };
}

async function renderFor(status: OrderStatus) {
  vi.mocked(ordersService.getDetail).mockResolvedValue(makeOrder(status));
  render(<OrderDetailPage orderId="o1" />);
  // Espera a que el detalle cargue (botones de transición dependen del status).
  await waitFor(() => {
    expect(
      screen.getByText(/Pendiente|Confirmado|Nuevo|Entregado|Cancelado/),
    ).toBeTruthy();
  });
}

const transitionButtons = () =>
  screen.queryAllByText(/^Pasar a /).map((el) => el.textContent ?? "");

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OrderDetailPage — botones de transición por estado (admin)", () => {
  it("new: solo 'Pasar a confirmado'", async () => {
    await renderFor("new");
    expect(transitionButtons()).toEqual(["Pasar a confirmado"]);
  });

  it("confirmed: 'Pasar a pendiente preparación' + 'Pasar a cancelado'", async () => {
    await renderFor("confirmed");
    expect(transitionButtons().sort()).toEqual(
      ["Pasar a cancelado", "Pasar a pendiente preparación"].sort(),
    );
  });

  it("preparing: 'Pasar a pendiente entrega' + 'Pasar a cancelado'", async () => {
    await renderFor("preparing");
    expect(transitionButtons().sort()).toEqual(
      ["Pasar a cancelado", "Pasar a pendiente entrega"].sort(),
    );
  });

  it("pending_delivery: solo 'Pasar a entregado' (no se cancela)", async () => {
    await renderFor("pending_delivery");
    expect(transitionButtons()).toEqual(["Pasar a entregado"]);
  });

  it("delivered (terminal): sin botones de transición", async () => {
    await renderFor("delivered");
    expect(transitionButtons()).toEqual([]);
  });

  it("cancelled (terminal): sin botones de transición", async () => {
    await renderFor("cancelled");
    expect(transitionButtons()).toEqual([]);
  });
});

import { fireEvent, screen, waitFor } from "@testing-library/react";
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
    confirmReceipt: vi.fn(),
    rejectReceipt: vi.fn(),
    deleteReceipt: vi.fn(),
  },
  receiptUrl: (orderId: string) => `/api/v1/orders/${orderId}/receipt`,
}));
vi.mock("@/modules/invoicing/service", () => ({
  invoicesService: { create: vi.fn(), downloadPdf: vi.fn() },
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

function makeOrder(
  status: OrderStatus,
  overrides: Partial<OrderDetail> = {},
): OrderDetail {
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
    payment_method: "cash",
    receipt_uploaded: false,
    receipt_content_type: null,
    receipt_uploaded_at: null,
    receipt_viewed_at: null,
    ...overrides,
  };
}

function transferOrder(overrides: Partial<OrderDetail> = {}): OrderDetail {
  return makeOrder("new", {
    payment_method: "transfer",
    receipt_uploaded: true,
    receipt_content_type: "image/jpeg",
    receipt_uploaded_at: "2026-11-25T12:00:00Z",
    receipt_viewed_at: null,
    ...overrides,
  });
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

describe("OrderDetailPage — comprobante de transferencia (S7)", () => {
  function renderDetail(detail: OrderDetail) {
    vi.mocked(ordersService.getDetail).mockResolvedValue(detail);
    render(<OrderDetailPage orderId="o1" />);
  }

  it("muestra el banner con preview de imagen y botones Confirmar/Rechazar", async () => {
    renderDetail(transferOrder());
    expect(
      await screen.findByText("Comprobante de transferencia cargado"),
    ).toBeInTheDocument();
    const img = screen.getByRole("img", { name: /comprobante/i });
    expect(img).toHaveAttribute("src", expect.stringContaining("/orders/o1/receipt"));
    expect(
      screen.getByRole("button", { name: "Confirmar comprobante" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Rechazar comprobante" }),
    ).toBeInTheDocument();
  });

  it("PDF: enlace en nueva pestaña en vez de preview inline", async () => {
    renderDetail(transferOrder({ receipt_content_type: "application/pdf" }));
    await screen.findByText("Comprobante de transferencia cargado");
    const link = screen.getByRole("link", { name: /ver comprobante/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("/orders/o1/receipt"));
    expect(link).toHaveAttribute("target", "_blank");
    expect(
      screen.queryByRole("img", { name: /comprobante/i }),
    ).not.toBeInTheDocument();
  });

  it("Confirmar: llama al endpoint y actualiza el detalle a pagado", async () => {
    vi.mocked(ordersService.confirmReceipt).mockResolvedValue(
      transferOrder({ paid: true }),
    );
    renderDetail(transferOrder());
    fireEvent.click(
      await screen.findByRole("button", { name: "Confirmar comprobante" }),
    );
    await waitFor(() =>
      expect(ordersService.confirmReceipt).toHaveBeenCalledWith("o1"),
    );
    expect(await screen.findByText("Pago registrado")).toBeInTheDocument();
  });

  it("Rechazar: diálogo de irreversibilidad (cancela el pedido) y llama al endpoint", async () => {
    vi.mocked(ordersService.rejectReceipt).mockResolvedValue(
      makeOrder("cancelled", { payment_method: "transfer", receipt_uploaded: true }),
    );
    renderDetail(transferOrder());
    fireEvent.click(
      await screen.findByRole("button", { name: "Rechazar comprobante" }),
    );
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/cancela/i);
    fireEvent.click(screen.getByRole("button", { name: "Rechazar" }));
    await waitFor(() =>
      expect(ordersService.rejectReceipt).toHaveBeenCalledWith("o1"),
    );
  });

  it("delivered: botón fantasma 'Borrar comprobante' con diálogo de confirmación", async () => {
    vi.mocked(ordersService.deleteReceipt).mockResolvedValue(undefined);
    renderDetail(transferOrder({ status: "delivered", paid: true }));
    expect(
      screen.queryByText("Comprobante de transferencia cargado"),
    ).not.toBeInTheDocument();
    fireEvent.click(
      await screen.findByRole("button", { name: "Borrar comprobante" }),
    );
    await screen.findByRole("alertdialog");
    fireEvent.click(screen.getByRole("button", { name: "Borrar" }));
    await waitFor(() =>
      expect(ordersService.deleteReceipt).toHaveBeenCalledWith("o1"),
    );
  });

  it("comprobante pendiente: sin botón 'Marcar pagado' (el flujo es el comprobante)", async () => {
    renderDetail(transferOrder());
    await screen.findByText("Comprobante de transferencia cargado");
    expect(
      screen.queryByRole("button", { name: "Marcar pagado" }),
    ).not.toBeInTheDocument();
  });

  it("transfer sin comprobante: 'Marcar pagado' deshabilitado con tooltip", async () => {
    renderDetail(makeOrder("new", { payment_method: "transfer" }));
    await waitFor(() =>
      expect(screen.getByText(/Nuevo|Confirmado/)).toBeTruthy(),
    );
    const btn = screen.getByRole("button", { name: "Marcar pagado" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("title", expect.stringMatching(/comprobante/i));
  });

  it("cash sin comprobante: 'Marcar pagado' habilitado", async () => {
    renderDetail(makeOrder("new"));
    const btn = await screen.findByRole("button", { name: "Marcar pagado" });
    expect(btn).toBeEnabled();
  });
});

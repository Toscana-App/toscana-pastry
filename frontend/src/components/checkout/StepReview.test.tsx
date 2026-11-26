import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { StepReview, CheckoutSuccess } from "./StepReview";
import type { CartResponse, OrderDetail } from "@/types/orders";

const analytics = vi.hoisted(() => ({ trackEvent: vi.fn() }));
const orders = vi.hoisted(() => ({
  createPortalOrder: vi.fn(),
  uploadOrderReceipt: vi.fn(),
}));
const toast = vi.hoisted(() => ({ create: vi.fn() }));

vi.mock("@/lib/analytics", () => ({
  trackEvent: analytics.trackEvent,
}));
vi.mock("@/services/ordersService", () => ({
  createPortalOrder: orders.createPortalOrder,
  uploadOrderReceipt: orders.uploadOrderReceipt,
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: toast.create },
}));

const CART: CartResponse = {
  audience: "consumidor_final",
  items: [
    {
      product_id: "p1",
      name: "Torta de chocolate",
      unit_price: "17500",
      qty: 1,
      total: "17500",
    },
  ],
  subtotal: "17500",
  total: "17500",
  discount_amount: "0",
  coupon: null,
};

const ORDER: OrderDetail = {
  id: "ord1",
  code: "#00001",
  customer_id: "c1",
  status: "new",
  date: "2026-11-25",
  payment_method: "cash",
  delivery_mode: "pickup",
  delivery_address: null,
  coupon_code: null,
  discount_amount: null,
  paid: false,
  payment_status: null,
  total: "17500",
  items: [],
  created_at: "2026-11-23T00:00:00Z",
  receipt_uploaded: false,
  receipt_content_type: null,
  receipt_uploaded_at: null,
  receipt_viewed_at: null,
};

function renderReview() {
  const onBack = vi.fn();
  const onConfirmed = vi.fn();
  renderWithProviders(
    <StepReview
      contact={{ name: "Ana", phone: "+5491155550000", email: "ana@test.com" }}
      address={null}
      delivery={{ date: "2026-11-25", delivery_mode: "pickup" }}
      payment={{ payment_method: "cash" }}
      cart={CART}
      onBack={onBack}
      onConfirmed={onConfirmed}
    />,
  );
  return { onBack, onConfirmed };
}

describe("StepReview (GA4)", () => {
  beforeEach(() => {
    analytics.trackEvent.mockClear();
    orders.createPortalOrder.mockReset();
    toast.create.mockClear();
  });

  it("dispara purchase junto a order_confirmed al confirmar el pedido", async () => {
    orders.createPortalOrder.mockResolvedValueOnce(ORDER);
    const user = userEvent.setup();
    const { onConfirmed } = renderReview();

    await user.click(screen.getByRole("button", { name: "Confirmar pedido" }));

    await waitFor(() =>
      expect(orders.createPortalOrder).toHaveBeenCalled(),
    );
    expect(onConfirmed).toHaveBeenCalledWith(ORDER);
    expect(analytics.trackEvent).toHaveBeenCalledWith(
      "order_confirmed",
      expect.objectContaining({ order_code: "#00001" }),
    );
    expect(analytics.trackEvent).toHaveBeenCalledWith("purchase", {
      transaction_id: "#00001",
      value: 17500,
      currency: "ARS",
      items: [
        {
          item_id: "p1",
          item_name: "Torta de chocolate",
          price: 17500,
          quantity: 1,
          currency: "ARS",
        },
      ],
      payment_method: "cash",
    });
  });

  it("no dispara purchase ni order_confirmed si el pedido falla", async () => {
    orders.createPortalOrder.mockRejectedValueOnce(
      new Error("order_window_closed"),
    );
    const user = userEvent.setup();
    renderReview();

    await user.click(screen.getByRole("button", { name: "Confirmar pedido" }));

    expect(
      await screen.findByText("La ventana de pedidos está cerrada"),
    ).toBeInTheDocument();
    expect(analytics.trackEvent).not.toHaveBeenCalledWith(
      "purchase",
      expect.anything(),
    );
    expect(analytics.trackEvent).not.toHaveBeenCalledWith(
      "order_confirmed",
      expect.anything(),
    );
  });
});

const TRANSFER_ORDER: OrderDetail = {
  ...ORDER,
  payment_method: "transfer",
};

describe("CheckoutSuccess (comprobante de transferencia)", () => {
  beforeEach(() => {
    orders.uploadOrderReceipt.mockReset();
    toast.create.mockClear();
  });

  function renderSuccess(order: OrderDetail) {
    renderWithProviders(<CheckoutSuccess order={order} />);
  }

  it("muestra la card de warning y el botón para transfer sin comprobante", () => {
    renderSuccess(TRANSFER_ORDER);
    expect(
      screen.getByText(
        "Para confirmar su pedido, por favor suba el comprobante de la transferencia.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Subir comprobante" }),
    ).toBeInTheDocument();
  });

  it("no muestra la card de comprobante para otros métodos", () => {
    renderSuccess(ORDER);
    expect(
      screen.queryByRole("button", { name: "Subir comprobante" }),
    ).not.toBeInTheDocument();
  });

  it("valida la extensión client-side y no envía archivos no aceptados", async () => {
    renderSuccess(TRANSFER_ORDER);
    // applyAccept: false simula el camino de drag & drop (el file dialog
    // real ya filtra por accept, pero el drop no)
    const user = userEvent.setup({ applyAccept: false });
    await user.click(screen.getByRole("button", { name: "Subir comprobante" }));
    const input = (await screen.findByLabelText(
      "Elegir archivo",
    )) as HTMLInputElement;
    await user.upload(
      input,
      new File(["notas"], "notas.txt", { type: "text/plain" }),
    );
    await user.click(screen.getByRole("button", { name: "Subir" }));
    await waitFor(() =>
      expect(screen.getByText(/Formato no aceptado/i)).toBeInTheDocument(),
    );
    expect(orders.uploadOrderReceipt).not.toHaveBeenCalled();
  });

  it("envía multipart y muestra la pantalla de espera tras 201", async () => {
    orders.uploadOrderReceipt.mockResolvedValueOnce({
      ...TRANSFER_ORDER,
      receipt_uploaded: true,
      receipt_content_type: "application/pdf",
      receipt_uploaded_at: "2026-11-25T12:00:00Z",
    });
    renderSuccess(TRANSFER_ORDER);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Subir comprobante" }));
    const input = (await screen.findByLabelText(
      "Elegir archivo",
    )) as HTMLInputElement;
    await user.upload(
      input,
      new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "comprobante.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Subir" }));
    await waitFor(() =>
      expect(orders.uploadOrderReceipt).toHaveBeenCalledTimes(1),
    );
    expect(orders.uploadOrderReceipt).toHaveBeenCalledWith(
      "ord1",
      expect.any(File),
    );
    expect(
      await screen.findByText("Comprobante en verificación"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("La verificación es manual y toma hasta 24 horas."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Subir comprobante" }),
    ).not.toBeInTheDocument();
  });

  it("muestra un toast si el envío falla", async () => {
    orders.uploadOrderReceipt.mockRejectedValueOnce(
      Object.assign(new Error("receipt_already_uploaded"), { status: 409 }),
    );
    renderSuccess(TRANSFER_ORDER);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Subir comprobante" }));
    const input = (await screen.findByLabelText(
      "Elegir archivo",
    )) as HTMLInputElement;
    await user.upload(
      input,
      new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "c.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Subir" }));
    await waitFor(() =>
      expect(toast.create).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      ),
    );
  });
});

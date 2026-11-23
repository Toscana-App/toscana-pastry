import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { StepReview } from "./StepReview";
import type { CartResponse, OrderDetail } from "@/types/orders";

const analytics = vi.hoisted(() => ({ trackEvent: vi.fn() }));
const orders = vi.hoisted(() => ({ createPortalOrder: vi.fn() }));
const toast = vi.hoisted(() => ({ create: vi.fn() }));

vi.mock("@/lib/analytics", () => ({
  trackEvent: analytics.trackEvent,
}));
vi.mock("@/services/ordersService", () => ({
  createPortalOrder: orders.createPortalOrder,
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
  status: "nuevo",
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

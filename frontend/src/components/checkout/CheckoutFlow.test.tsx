import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test-utils";
import { CheckoutFlow } from "./CheckoutFlow";
import type { CartResponse } from "@/types/orders";

const analytics = vi.hoisted(() => ({ trackEvent: vi.fn() }));
const services = vi.hoisted(() => ({
  fetchCart: vi.fn(),
  fetchMyAddresses: vi.fn(),
}));
const toast = vi.hoisted(() => ({ create: vi.fn() }));

vi.mock("@/lib/analytics", () => ({
  trackEvent: analytics.trackEvent,
}));
vi.mock("@/services/cartService", () => ({
  fetchCart: services.fetchCart,
}));
vi.mock("@/services/ordersService", () => ({
  fetchMyAddresses: services.fetchMyAddresses,
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: toast.create },
}));
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { role: "customer", email: "cliente@test.com" } }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
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

describe("CheckoutFlow (GA4)", () => {
  beforeEach(() => {
    analytics.trackEvent.mockClear();
    services.fetchCart.mockReset();
    services.fetchMyAddresses.mockReset();
    toast.create.mockClear();
  });

  it("dispara begin_checkout una vez con value, currency e items del carrito", async () => {
    services.fetchCart.mockResolvedValue(CART);
    services.fetchMyAddresses.mockResolvedValue({ items: [] });

    renderWithProviders(<CheckoutFlow />);

    await screen.findByText("Finalizar pedido");
    await waitFor(() =>
      expect(analytics.trackEvent).toHaveBeenCalledWith("begin_checkout", {
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
      }),
    );
    expect(analytics.trackEvent).toHaveBeenCalledTimes(1);
  });

  it("no dispara begin_checkout con carrito vacío", async () => {
    services.fetchCart.mockResolvedValue({ ...CART, items: [] });
    services.fetchMyAddresses.mockResolvedValue({ items: [] });

    renderWithProviders(<CheckoutFlow />);

    expect(
      await screen.findByText("Tu carrito está vacío"),
    ).toBeInTheDocument();
    expect(analytics.trackEvent).not.toHaveBeenCalledWith(
      "begin_checkout",
      expect.anything(),
    );
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test-utils";
import { ProductStoreDetail } from "./ProductStoreDetail";

const store = vi.hoisted(() => ({
  detail: vi.fn(),
}));
const cart = vi.hoisted(() => ({ add: vi.fn() }));
const toast = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
}));
const analytics = vi.hoisted(() => ({ trackEvent: vi.fn() }));

vi.mock("@/services/storeService", () => ({
  fetchStoreDetail: store.detail,
}));
vi.mock("@/services/cartService", () => ({
  addCartItem: cart.add,
}));
vi.mock("goey-toast", () => ({ gooeyToast: toast }));
vi.mock("@/lib/analytics", () => ({
  trackEvent: analytics.trackEvent,
}));
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { role: "customer" } }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

const DETAIL = {
  id: "p1",
  name: "Torta de chocolate",
  category: "Tortas",
  description: "Bizcochuel húmedo, cobertura de chocolate.",
  image_url: "/media/products/p1.jpg",
  price: "17500",
  servings: 12,
  prep_time_min: 90,
  tags: ["sin gluten", "vegano"],
};

describe("ProductStoreDetail (portal)", () => {
  beforeEach(() => {
    store.detail.mockReset();
    cart.add.mockReset();
    toast.success.mockClear();
    toast.error.mockClear();
    analytics.trackEvent.mockClear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("muestra imagen, categoría, descripción, porciones, tiempo y precio", async () => {
    store.detail.mockResolvedValueOnce(DETAIL);

    renderWithProviders(<ProductStoreDetail id="p1" />);

    expect(await screen.findByText("Torta de chocolate")).toBeInTheDocument();
    expect(screen.getByText("Tortas")).toBeInTheDocument();
    expect(
      screen.getByText("Bizcochuel húmedo, cobertura de chocolate."),
    ).toBeInTheDocument();
    expect(screen.getByText(/12 porciones/)).toBeInTheDocument();
    expect(screen.getByText(/90 min/)).toBeInTheDocument();
    expect(screen.getByText(/17.500/)).toBeInTheDocument();
    expect(
      screen.getByAltText("Imagen de Torta de chocolate"),
    ).toBeInTheDocument();
  });

  it("agrega al carrito con el id del producto", async () => {
    store.detail.mockResolvedValueOnce(DETAIL);
    cart.add.mockResolvedValueOnce({});
    const user = userEvent.setup();

    renderWithProviders(<ProductStoreDetail id="p1" />);
    await screen.findByText("Torta de chocolate");

    await user.click(screen.getByRole("button", { name: /al carrito/i }));

    expect(cart.add).toHaveBeenCalledWith("p1", 1);
    expect(toast.success).toHaveBeenCalled();
  });

  it("dispara view_item con el shape GA4 tras cargar el detalle", async () => {
    store.detail.mockResolvedValueOnce(DETAIL);

    renderWithProviders(<ProductStoreDetail id="p1" />);
    await screen.findByText("Torta de chocolate");

    expect(analytics.trackEvent).toHaveBeenCalledWith("view_item", {
      item: {
        item_id: "p1",
        item_name: "Torta de chocolate",
        price: 17500,
        quantity: 1,
        currency: "ARS",
      },
    });
  });

  it("dispara select_item y add_to_cart tras agregar al carrito con éxito", async () => {
    store.detail.mockResolvedValueOnce(DETAIL);
    cart.add.mockResolvedValueOnce({});
    const user = userEvent.setup();

    renderWithProviders(<ProductStoreDetail id="p1" />);
    await screen.findByText("Torta de chocolate");
    await user.click(screen.getByRole("button", { name: /al carrito/i }));

    expect(analytics.trackEvent).toHaveBeenCalledWith("select_item", {
      item: expect.objectContaining({
        item_id: "p1",
        price: 17500,
        quantity: 1,
        currency: "ARS",
      }),
    });
    expect(analytics.trackEvent).toHaveBeenCalledWith("add_to_cart", {
      item: expect.objectContaining({
        item_id: "p1",
        price: 17500,
        quantity: 1,
        currency: "ARS",
      }),
    });
  });

  it("no dispara select_item ni add_to_cart si agregar al carrito falla", async () => {
    store.detail.mockResolvedValueOnce(DETAIL);
    cart.add.mockRejectedValueOnce(new Error("cart_error"));
    const user = userEvent.setup();

    renderWithProviders(<ProductStoreDetail id="p1" />);
    await screen.findByText("Torta de chocolate");
    await user.click(screen.getByRole("button", { name: /al carrito/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(analytics.trackEvent).not.toHaveBeenCalledWith(
      "select_item",
      expect.anything(),
    );
    expect(analytics.trackEvent).not.toHaveBeenCalledWith(
      "add_to_cart",
      expect.anything(),
    );
  });

  it("muestra un estado amable cuando el producto no está disponible (404)", async () => {
    store.detail.mockRejectedValueOnce(new Error("product_not_found"));

    renderWithProviders(<ProductStoreDetail id="p1" />);

    expect(
      await screen.findByText(/no está disponible/),
    ).toBeInTheDocument();
  });
});

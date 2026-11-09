import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
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

vi.mock("@/services/storeService", () => ({
  fetchStoreDetail: store.detail,
}));
vi.mock("@/services/cartService", () => ({
  addCartItem: cart.add,
}));
vi.mock("goey-toast", () => ({ gooeyToast: toast }));
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
};

describe("ProductStoreDetail (portal)", () => {
  beforeEach(() => {
    store.detail.mockReset();
    cart.add.mockReset();
    toast.success.mockClear();
    toast.error.mockClear();
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

  it("muestra un estado amable cuando el producto no está disponible (404)", async () => {
    store.detail.mockRejectedValueOnce(new Error("product_not_found"));

    renderWithProviders(<ProductStoreDetail id="p1" />);

    expect(
      await screen.findByText(/no está disponible/),
    ).toBeInTheDocument();
  });
});

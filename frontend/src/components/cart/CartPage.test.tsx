import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders as render } from "../../test-utils";
import CartPage from "./CartPage";
import type { CartResponse } from "@/types/orders";

// Mock Next.js router
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
}));

// Seams: cart service functions and toaster.
vi.mock("@/services/cartService", () => ({
  fetchCart: vi.fn(),
  addCartItem: vi.fn(),
  removeCartItem: vi.fn(),
  applyCoupon: vi.fn(),
  removeCoupon: vi.fn(),
}));
vi.mock("@/lib/toaster", () => ({
  toaster: { create: vi.fn() },
}));

import { fetchCart, addCartItem, removeCartItem, applyCoupon, removeCoupon } from "@/services/cartService";

const mockCart: CartResponse = {
  audience: "customer",
  items: [
    {
      product_id: "prod-1",
      name: "Torta",
      unit_price: "1000.00",
      qty: 2,
      total: "2000.00",
    },
    {
      product_id: "prod-2",
      name: "Alfajor",
      unit_price: "200.00",
      qty: 1,
      total: "200.00",
    },
  ],
  subtotal: "2200.00",
  total: "2200.00",
  discount_amount: "0.00",
  coupon: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchCart).mockResolvedValue(mockCart);
  vi.mocked(addCartItem).mockResolvedValue(mockCart);
  vi.mocked(removeCartItem).mockResolvedValue(mockCart);
  vi.mocked(applyCoupon).mockResolvedValue(mockCart);
  vi.mocked(removeCoupon).mockResolvedValue(mockCart);
});

describe("CartPage", () => {
  it("should render cart with items", async () => {
    // Set up the mock BEFORE rendering
    vi.mocked(fetchCart).mockResolvedValue(mockCart);
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText("Tu carrito")).toBeInTheDocument();
      expect(screen.getByText("Torta")).toBeInTheDocument();
      expect(screen.getByText("Alfajor")).toBeInTheDocument();
    });
  });

  it("should show empty cart when no items", async () => {
    const emptyCart: CartResponse = {
      audience: "customer",
      items: [],
      subtotal: "0.00",
      total: "0.00",
      discount_amount: "0.00",
      coupon: null,
    };
    vi.mocked(fetchCart).mockResolvedValue(emptyCart);
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText("Tu carrito está vacío")).toBeInTheDocument();
    });
  });

  it("should increase item quantity when plus button clicked", async () => {
    // Set up the mock BEFORE rendering
    vi.mocked(fetchCart).mockResolvedValue(mockCart);
    
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByText("Torta")).toBeInTheDocument();
    });
    
    const plusButton = screen.getAllByRole("button", { name: /Agregar un Torta/ })[0];
    fireEvent.click(plusButton);
    
    await waitFor(() => {
      expect(addCartItem).toHaveBeenCalledWith("prod-1", 3);
    });
  });

  it("should apply coupon when form submitted", async () => {
    render(<CartPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Código de cupón")).toBeInTheDocument();
    });
    
    const couponInput = screen.getByPlaceholderText("Código de cupón");
    const applyButton = screen.getByRole("button", { name: /Aplicar/ });
    
    fireEvent.change(couponInput, { target: { value: "DESCUENTO10" } });
    fireEvent.click(applyButton);
    
    await waitFor(() => {
      expect(applyCoupon).toHaveBeenCalledWith("DESCUENTO10");
    });
  });
});
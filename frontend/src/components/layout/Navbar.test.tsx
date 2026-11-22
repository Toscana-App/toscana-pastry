import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { Navbar } from "./Navbar";

const usePathname = vi.hoisted(() => vi.fn(() => "/"));
const authState = vi.hoisted(() => ({
  user: null as { email: string; role: string } | null,
  logout: vi.fn(),
}));
const cartCount = vi.hoisted(() => ({ value: 0 }));

vi.mock("next/navigation", () => ({
  usePathname: () => usePathname(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: authState.user,
    isAuthenticated: authState.user !== null,
    logout: authState.logout,
  }),
}));

vi.mock("@/hooks/useCartCount", () => ({
  useCartCount: () => cartCount.value,
}));

describe("Navbar", () => {
  beforeEach(() => {
    authState.user = null;
    authState.logout = vi.fn();
    cartCount.value = 0;
    usePathname.mockReturnValue("/");
  });

  it("hides itself on /login (no duplicate logo or redundant Login link)", () => {
    usePathname.mockReturnValue("/login");
    const { container } = renderWithProviders(<Navbar />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the logo and links on other routes", () => {
    renderWithProviders(<Navbar />);
    expect(screen.getAllByRole("link").length).toBeGreaterThan(0);
  });

  it("does not render the search bar (search lives only in the hero)", () => {
    const { container } = renderWithProviders(<Navbar />);
    expect(container.querySelector('form[role="search"]')).toBeNull();
  });

  it("shows a Login link when logged out", () => {
    renderWithProviders(<Navbar />);
    expect(screen.getByRole("link", { name: "Login" })).toHaveAttribute(
      "href",
      "/login"
    );
  });

  it("exposes admin options inside a menu, keeping their routes", async () => {
    authState.user = { email: "ana@toscana.com", role: "admin" };
    renderWithProviders(<Navbar />);
    expect(screen.queryByRole("menuitem", { name: "Pedidos" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Menú" }));
    expect(screen.getByRole("menuitem", { name: "Pedidos" })).toHaveAttribute(
      "href",
      "/pedidos"
    );
    expect(
      screen.getByRole("menuitem", { name: "Panel de control" })
    ).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("menuitem", { name: "Settings" })).toHaveAttribute(
      "href",
      "/admin/settings"
    );
  });

  it("uses an Avatar as the profile menu trigger and logs out from it (admin)", async () => {
    authState.user = { email: "ana@toscana.com", role: "admin" };
    renderWithProviders(<Navbar />);
    const trigger = screen.getByRole("button", { name: "Perfil" });
    expect(trigger.querySelector('[data-scope="avatar"]')).not.toBeNull();
    await userEvent.click(trigger);
    expect(screen.getByRole("menuitem", { name: "Perfil" })).toHaveAttribute(
      "href",
      "/profile"
    );
    await userEvent.click(screen.getByRole("menuitem", { name: "Logout" }));
    expect(authState.logout).toHaveBeenCalledTimes(1);
  });

  it("gives portal users a profile avatar menu without admin options or logout", async () => {
    authState.user = { email: "cli@toscana.com", role: "customer" };
    renderWithProviders(<Navbar />);
    expect(screen.queryByRole("button", { name: "Menú" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Mi cuenta" }));
    expect(
      screen.getByRole("menuitem", { name: "Mi cuenta" })
    ).toHaveAttribute("href", "/profile");
    expect(screen.queryByRole("menuitem", { name: "Logout" })).toBeNull();
  });

  it("anchors the cart count badge to the cart button corner", () => {
    authState.user = { email: "cli@toscana.com", role: "customer" };
    cartCount.value = 3;
    renderWithProviders(<Navbar />);
    const cart = screen.getByRole("link", { name: "Carrito" });
    const anchor = screen.getByText("3").parentElement as HTMLElement;
    expect(cart).toContainElement(anchor);
    expect(getComputedStyle(anchor).position).toBe("absolute");
    expect(getComputedStyle(anchor).insetBlockStart).toBe("0px");
    expect(getComputedStyle(anchor).insetInlineEnd).toBe("0px");
  });

  it("caps the cart badge at 99+ and hides it when empty", () => {
    authState.user = { email: "cli@toscana.com", role: "customer" };
    cartCount.value = 120;
    const { unmount } = renderWithProviders(<Navbar />);
    expect(screen.getByText("99+")).toBeInTheDocument();
    unmount();
    cartCount.value = 0;
    renderWithProviders(<Navbar />);
    expect(screen.queryByText("99+")).toBeNull();
  });
});

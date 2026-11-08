import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test-utils";
import { Navbar } from "./Navbar";

const usePathname = vi.hoisted(() => vi.fn(() => "/"));

vi.mock("next/navigation", () => ({
  usePathname: () => usePathname(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: null, isAuthenticated: false, logout: vi.fn() }),
}));

describe("Navbar", () => {
  it("hides itself on /login (no duplicate logo or redundant Login link)", () => {
    usePathname.mockReturnValue("/login");
    const { container } = renderWithProviders(<Navbar />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the logo and links on other routes", () => {
    usePathname.mockReturnValue("/");
    renderWithProviders(<Navbar />);
    expect(screen.getAllByRole("link").length).toBeGreaterThan(0);
  });
});

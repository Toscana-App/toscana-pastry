import { describe, expect, it, vi } from "vitest"
import { screen, within } from "@testing-library/react"
import { renderWithProviders } from "@/test-utils"
import { HERO_ATTRIBUTES, HeroSection } from "./hero_section"

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u-1", email: "cliente@test", role: "customer" },
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("HeroSection", () => {
  it("opens the portal with a single level-1 heading", () => {
    renderWithProviders(<HeroSection />)

    const heading = screen.getByRole("heading", { level: 1 })
    expect(heading).toHaveTextContent("Pastelería natural,")
    expect(heading).toHaveTextContent("para cada momento.")
  })

  it("points its one action at the catalog below and offers orders as a text link", () => {
    renderWithProviders(<HeroSection />)

    expect(screen.getByRole("link", { name: /ver el catálogo/i })).toHaveAttribute("href", "#catalogo")
    expect(screen.getByRole("link", { name: /mirá tus pedidos/i })).toHaveAttribute("href", "/my-orders")
  })

  it("includes its own navbar row with the product search bar", () => {
    renderWithProviders(<HeroSection />)

    const search = screen.getByRole("search")
    expect(within(search).getByRole("searchbox", { name: /buscar productos/i })).toBeInTheDocument()
    expect(within(search).getByRole("button", { name: "Buscar" })).toBeInTheDocument()
  })

  it("keeps the Buscar button outside the input, to its right", () => {
    renderWithProviders(<HeroSection />)

    const search = screen.getByRole("search")
    const input = within(search).getByRole("searchbox", { name: /buscar productos/i })
    const button = within(search).getByRole("button", { name: "Buscar" })
    const inputGroup = input.parentElement
    expect(inputGroup?.contains(button)).toBe(false)
    expect(button.parentElement?.contains(inputGroup)).toBe(true)
  })

  it("lists every product attribute with its status in the ledger panel", () => {
    renderWithProviders(<HeroSection />)

    const list = screen.getByRole("list", { name: /etiquetas del catálogo/i })
    const rows = within(list).getAllByRole("listitem")
    expect(rows).toHaveLength(HERO_ATTRIBUTES.length)
    HERO_ATTRIBUTES.forEach(({ label, status }, index) => {
      expect(rows[index]).toHaveTextContent(label.replace(/ /g, " "))
      expect(rows[index]).toHaveTextContent(status.replace(/ /g, " "))
    })
  })
})

import { describe, expect, it } from "vitest"
import { screen, within } from "@testing-library/react"
import { renderWithProviders } from "@/test-utils"
import { HERO_ATTRIBUTES, HeroSection } from "./hero_section"

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

  it("lists every product attribute with its status in the ledger panel", () => {
    renderWithProviders(<HeroSection />)

    const list = screen.getByRole("list", { name: /etiquetas del catálogo/i })
    const rows = within(list).getAllByRole("listitem")
    expect(rows).toHaveLength(HERO_ATTRIBUTES.length)
    HERO_ATTRIBUTES.forEach(({ label, status }, index) => {
      expect(rows[index]).toHaveTextContent(label)
      expect(rows[index]).toHaveTextContent(status)
    })
  })
})

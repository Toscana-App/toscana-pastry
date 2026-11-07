import { describe, expect, it } from "vitest"
import { screen } from "@testing-library/react"
import { renderWithProviders } from "@/test-utils"
import { BrandLogo } from "./BrandLogo"

describe("BrandLogo", () => {
  it("ships an ink logo for light mode and a cream one for dark mode", () => {
    renderWithProviders(<BrandLogo variant="horizontal" height={36} />)

    expect(screen.getAllByRole("img", { name: "Toscana" })).toHaveLength(1)
    const sources = screen.getAllByAltText("Toscana").map((img) => img.getAttribute("src"))
    expect(sources).toHaveLength(2)
    expect(sources.some((src) => src?.includes("logo_horizontal_ink"))).toBe(true)
    expect(sources.some((src) => src?.includes("logo_horizontal_cream"))).toBe(true)
  })

  it("uses the tagline lockup for the vertical variant", () => {
    renderWithProviders(<BrandLogo variant="vertical" height={180} />)

    const sources = screen.getAllByAltText("Toscana, horneando momentos").map((img) => img.getAttribute("src"))
    expect(sources).toHaveLength(2)
    expect(sources.every((src) => src?.includes("logo_vertical_tagline"))).toBe(true)
  })
})

import { describe, expect, it } from "vitest"
import { system } from "./theme"

// Chakra v3 colorPalette recipes read these semantic keys; without them
// `colorPalette="brand"` renders with no fill or contrast color.
const PALETTE_KEYS = ["solid", "contrast", "fg", "muted", "subtle", "emphasized", "focusRing"]

describe("theme system", () => {
  it.each(PALETTE_KEYS)("defines the brand.%s semantic color", (key) => {
    expect(system.tokens.getByName(`colors.brand.${key}`)).toBeDefined()
  })

  it.each(["body", "heading"])("uses SN Pro for the %s font", (font) => {
    expect(system.tokens.getByName(`fonts.${font}`)?.value).toContain("var(--font-sn-pro)")
  })
})

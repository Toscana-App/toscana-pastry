import { describe, expect, it } from "vitest"
import { system } from "./theme"

const PALETTE_KEYS = ["solid", "contrast", "fg", "muted", "subtle", "emphasized", "focusRing"]

type Mode = "_light" | "_dark"
const MODES: Mode[] = ["_light", "_dark"]

function resolve(name: string, mode: Mode): string {
  const token = system.tokens.getByName(name.startsWith("colors.") ? name : `colors.${name}`)
  if (!token) throw new Error(`unknown token ${name}`)
  const raw: string = token.extensions?.conditions?.[mode] ?? token.originalValue
  const ref = /^\{(.+)\}$/.exec(raw)
  if (ref) return resolve(ref[1], mode)
  return raw.startsWith("#") ? raw : resolve(raw, mode)
}

function luminance(hex: string): number {
  const full = hex.length === 4 ? hex.replace(/(\w)/g, "$1$1") : hex
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(full.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(fg: string, bg: string, mode: Mode): number {
  const [a, b] = [luminance(resolve(fg, mode)), luminance(resolve(bg, mode))]
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

const SURFACES = ["bg", "bg.panel", "bg.subtle", "bg.muted"]
const TEXT_ON_SURFACES = ["fg", "fg.muted", "brand.fg", "red.fg", "green.fg", "orange.fg", "blue.fg", "fg.error", "fg.success", "fg.warning"]
const PALETTES = ["brand", "red", "green", "orange", "blue", "gray"]

const PAIRS: [string, string][] = [
  ...TEXT_ON_SURFACES.flatMap((fg) => SURFACES.map((bg) => [fg, bg] as [string, string])),
  ...PALETTES.map((p) => [`${p}.contrast`, `${p}.solid`] as [string, string]),
  ...PALETTES.map((p) => [`${p}.fg`, `${p}.subtle`] as [string, string]),
  ...PALETTES.map((p) => [`${p}.fg`, `${p}.muted`] as [string, string]),
]

describe("theme system", () => {
  it.each(PALETTE_KEYS)("defines the brand.%s semantic color", (key) => {
    expect(system.tokens.getByName(`colors.brand.${key}`)).toBeDefined()
  })

  it.each(PALETTE_KEYS)("gives brand.%s a dark-mode value", (key) => {
    const conditions = system.tokens.getByName(`colors.brand.${key}`)?.extensions?.conditions
    expect(conditions?._dark).toBeDefined()
  })

  it.each(["body", "heading"])("uses SN Pro for the %s font", (font) => {
    expect(system.tokens.getByName(`fonts.${font}`)?.value).toContain("var(--font-sn-pro)")
  })
})

describe("palette contrast (WCAG AA)", () => {
  it.each(MODES.flatMap((mode) => PAIRS.map(([fg, bg]) => [mode, fg, bg] as const)))(
    "%s: %s on %s reaches 4.5:1",
    (mode, fg, bg) => {
      expect(contrast(fg, bg, mode)).toBeGreaterThanOrEqual(4.5)
    },
  )

  it("uses a dark, non-black canvas in dark mode with elevated panels above it", () => {
    const canvas = luminance(resolve("bg", "_dark"))
    const panel = luminance(resolve("bg.panel", "_dark"))
    expect(resolve("bg", "_dark").toLowerCase()).not.toBe("#000000")
    expect(canvas).toBeLessThan(0.02)
    expect(panel).toBeGreaterThan(canvas)
  })

  it("lifts panels above the canvas in light mode too", () => {
    expect(resolve("bg.panel", "_light").toLowerCase()).not.toBe(resolve("bg", "_light").toLowerCase())
  })
})

describe("brand colors", () => {
  it.each([
    ["toscana.coral", "#ff7078"],
    ["toscana.peach", "#f5ccad"],
    ["toscana.sage", "#cce0c9"],
    ["toscana.teal", "#75bda3"],
  ])("defines %s as %s", (name, hex) => {
    expect(resolve(name, "_light")).toBe(hex)
  })

  it.each(MODES)("fills primary actions with the exact brand coral (%s)", (mode) => {
    expect(resolve("brand.solid", mode)).toBe("#ff7078")
  })

  it.each(MODES)("fills positive states with the brand teal (%s)", (mode) => {
    expect(resolve("green.solid", mode)).toBe("#75bda3")
  })
})

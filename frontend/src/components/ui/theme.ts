import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

// SN Pro is loaded by next/font in app/layout.tsx and exposed as this variable.
const FONT_STACK = `var(--font-sn-pro), -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif`

/**
 * Palette: every semantic role has a composed light AND dark value (dark is
 * designed, not inverted). Light = zinc paper with white panels lifted off a
 * #fafafa canvas. Dark = near-black canvas with a faint indigo cast; panels
 * step up in lightness to show elevation. Text and status pairs are pinned
 * to WCAG AA by theme.test.ts.
 */
const customConfig = defineConfig({
  theme: {
    tokens: {
      fonts: {
        heading: { value: FONT_STACK },
        body: { value: FONT_STACK },
      },
      colors: {
        brand: {
          50: { value: "#eef2ff" },
          100: { value: "#e0e7ff" },
          200: { value: "#c7d2fe" },
          300: { value: "#a5b4fc" },
          400: { value: "#818cf8" },
          500: { value: "#6366f1" },
          600: { value: "#4f46e5" },
          700: { value: "#4338ca" },
          800: { value: "#3730a3" },
          900: { value: "#312e81" },
          950: { value: "#1e1b4b" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: { _light: "#fafafa", _dark: "#0c0c12" } },
          subtle: { value: { _light: "#f4f4f5", _dark: "#111119" } },
          panel: { value: { _light: "#ffffff", _dark: "#15151d" } },
          muted: { value: { _light: "#efeff1", _dark: "#1c1c26" } },
          emphasized: { value: { _light: "#e4e4e7", _dark: "#282834" } },
        },
        fg: {
          DEFAULT: { value: { _light: "#0a0a0f", _dark: "#f4f4f7" } },
          muted: { value: { _light: "#52525b", _dark: "#a3a3b2" } },
          // Placeholder/disabled tier only; not for body copy.
          subtle: { value: { _light: "#71717a", _dark: "#75758a" } },
          // Chakra defaults (500/600 in light) fail 4.5:1 on white.
          error: { value: { _light: "{colors.red.700}", _dark: "{colors.red.300}" } },
          success: { value: { _light: "{colors.green.700}", _dark: "{colors.green.300}" } },
          warning: { value: { _light: "{colors.orange.700}", _dark: "{colors.orange.300}" } },
        },
        border: {
          DEFAULT: { value: { _light: "#e4e4e7", _dark: "#2a2a37" } },
          muted: { value: { _light: "#efeff1", _dark: "#1f1f2a" } },
          subtle: { value: { _light: "#f4f4f5", _dark: "#17171f" } },
          emphasized: { value: { _light: "#d4d4d8", _dark: "#3c3c4c" } },
        },
        // Keys read by Chakra's colorPalette recipes. solid stays 600 in both
        // modes: white on #6366f1 (500) is 4.47:1 and fails WCAG AA.
        brand: {
          solid: { value: { _light: "{colors.brand.600}", _dark: "{colors.brand.600}" } },
          contrast: { value: { _light: "{colors.white}", _dark: "{colors.white}" } },
          fg: { value: { _light: "{colors.brand.700}", _dark: "{colors.brand.300}" } },
          muted: { value: { _light: "{colors.brand.100}", _dark: "{colors.brand.900}" } },
          subtle: { value: { _light: "{colors.brand.50}", _dark: "{colors.brand.950}" } },
          emphasized: { value: { _light: "{colors.brand.200}", _dark: "{colors.brand.800}" } },
          focusRing: { value: { _light: "{colors.brand.500}", _dark: "{colors.brand.400}" } },
        },
        // Status fills: Chakra's defaults put white text under 4.5:1.
        red: { solid: { value: { _light: "{colors.red.600}", _dark: "{colors.red.600}" } } },
        green: { solid: { value: { _light: "{colors.green.700}", _dark: "{colors.green.700}" } } },
        orange: {
          solid: { value: { _light: "{colors.orange.700}", _dark: "{colors.orange.700}" } },
          contrast: { value: { _light: "{colors.white}", _dark: "{colors.white}" } },
        },
        blue: { solid: { value: { _light: "{colors.blue.600}", _dark: "{colors.blue.600}" } } },
      },
    },
  },
})

export const system = createSystem(defaultConfig, customConfig)

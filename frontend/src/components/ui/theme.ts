import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

// SN Pro is loaded by next/font in app/layout.tsx and exposed as this variable.
const FONT_STACK = `var(--font-sn-pro), -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif`

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
        // Keys read by Chakra's colorPalette recipes. solid is 600, not 500:
        // white on #6366f1 is 4.47:1 and fails WCAG AA.
        brand: {
          solid: { value: "{colors.brand.600}" },
          contrast: { value: "{colors.white}" },
          fg: { value: "{colors.brand.700}" },
          muted: { value: "{colors.brand.100}" },
          subtle: { value: "{colors.brand.50}" },
          emphasized: { value: "{colors.brand.200}" },
          focusRing: { value: "{colors.brand.500}" },
        },
      },
    },
  },
})

export const system = createSystem(defaultConfig, customConfig)

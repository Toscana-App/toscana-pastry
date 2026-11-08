import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

const FONT_STACK = `var(--font-sn-pro), -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif`

const customConfig = defineConfig({
  theme: {
    keyframes: {
      "hero-rise": {
        from: { opacity: "0", transform: "translateY(24px)" },
        to: { opacity: "1", transform: "translateY(0)" },
      },
      "hero-slide": {
        from: { opacity: "0", transform: "translateX(32px)" },
        to: { opacity: "1", transform: "translateX(0)" },
      },
    },
    tokens: {
      fonts: {
        heading: { value: FONT_STACK },
        body: { value: FONT_STACK },
      },
      colors: {
        brand: {
          50: { value: "#fff4f4" },
          100: { value: "#ffe4e5" },
          200: { value: "#ffccce" },
          300: { value: "#ffa4a9" },
          400: { value: "{colors.toscana.coral}" },
          500: { value: "#f74a55" },
          600: { value: "#e02d3b" },
          700: { value: "#bc1f2e" },
          800: { value: "#9c1d2a" },
          900: { value: "#821d29" },
          950: { value: "#470a11" },
        },
        toscana: {
          coral: { value: "#ff7078" },
          peach: { value: "#f5ccad" },
          sage: { value: "#cce0c9" },
          teal: { value: "#75bda3" },
        },
      },
    },
    semanticTokens: {
      colors: {
        bg: {
          DEFAULT: { value: { _light: "#fbf8f6", _dark: "#110e0e" } },
          subtle: { value: { _light: "#f6f1ee", _dark: "#161212" } },
          panel: { value: { _light: "#ffffff", _dark: "#1b1616" } },
          muted: { value: { _light: "#f1ebe7", _dark: "#231d1c" } },
          emphasized: { value: { _light: "#e7dfda", _dark: "#2f2826" } },
        },
        fg: {
          DEFAULT: { value: { _light: "#1c1718", _dark: "#f7f1ee" } },
          muted: { value: { _light: "#5e5553", _dark: "#b0a5a2" } },
          subtle: { value: { _light: "#7d7371", _dark: "#807573" } },
          error: { value: { _light: "{colors.red.700}", _dark: "{colors.red.300}" } },
          success: { value: { _light: "{colors.green.fg}", _dark: "{colors.green.fg}" } },
          warning: { value: { _light: "{colors.orange.700}", _dark: "{colors.orange.300}" } },
        },
        border: {
          DEFAULT: { value: { _light: "#e7dfda", _dark: "#322a29" } },
          muted: { value: { _light: "#f1ebe7", _dark: "#261f1e" } },
          subtle: { value: { _light: "#f6f1ee", _dark: "#1d1817" } },
          emphasized: { value: { _light: "#d6ccc7", _dark: "#463c3a" } },
        },
        brand: {
          solid: { value: { _light: "{colors.brand.400}", _dark: "{colors.brand.400}" } },
          contrast: { value: { _light: "#2a1215", _dark: "#2a1215" } },
          fg: { value: { _light: "{colors.brand.800}", _dark: "{colors.brand.300}" } },
          muted: { value: { _light: "{colors.toscana.peach}", _dark: "{colors.brand.900}" } },
          subtle: { value: { _light: "{colors.brand.50}", _dark: "{colors.brand.950}" } },
          emphasized: { value: { _light: "{colors.brand.200}", _dark: "{colors.brand.800}" } },
          focusRing: { value: { _light: "{colors.brand.500}", _dark: "{colors.brand.400}" } },
        },
        green: {
          solid: { value: { _light: "{colors.toscana.teal}", _dark: "{colors.toscana.teal}" } },
          contrast: { value: { _light: "#10251d", _dark: "#10251d" } },
          fg: { value: { _light: "#29664f", _dark: "#9fd8c3" } },
          muted: { value: { _light: "{colors.toscana.sage}", _dark: "#183128" } },
          subtle: { value: { _light: "#eef6ec", _dark: "#0f201a" } },
          emphasized: { value: { _light: "#b3d3ae", _dark: "#21443a" } },
          focusRing: { value: { _light: "{colors.toscana.teal}", _dark: "{colors.toscana.teal}" } },
        },
        red: { solid: { value: { _light: "{colors.red.600}", _dark: "{colors.red.600}" } } },
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

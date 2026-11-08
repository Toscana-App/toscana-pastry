---
name: Toscana Pastry
description: Design system for the Toscana Pastry shop tool (admin + customer portal), built on Chakra UI v3 plus the Toscana brand palette and official logo.
colors:
  toscana-coral: "#ff7078"
  coral-ink: "#2a1215"
  coral-text: "#9c1d2a"
  coral-text-dark: "#ffa4a9"
  coral-wash: "#fff4f4"
  coral-wash-dark: "#470a11"
  toscana-peach: "#f5ccad"
  toscana-peach-dark: "#821d29"
  coral-emphasized: "#ffccce"
  coral-emphasized-dark: "#9c1d2a"
  focus-ring: "#f74a55"
  focus-ring-dark: "#ff7078"
  toscana-teal: "#75bda3"
  teal-ink: "#10251d"
  toscana-sage: "#cce0c9"
  toscana-sage-dark: "#183128"
  sage-wash: "#eef6ec"
  sage-wash-dark: "#0f201a"
  canvas: "#fbf8f6"
  canvas-dark: "#110e0e"
  surface-subtle: "#f6f1ee"
  surface-subtle-dark: "#161212"
  panel: "#ffffff"
  panel-dark: "#1b1616"
  surface-muted: "#f1ebe7"
  surface-muted-dark: "#231d1c"
  surface-emphasized: "#e7dfda"
  surface-emphasized-dark: "#2f2826"
  ink: "#1c1718"
  ink-dark: "#f7f1ee"
  ink-muted: "#5e5553"
  ink-muted-dark: "#b0a5a2"
  ink-subtle: "#7d7371"
  ink-subtle-dark: "#807573"
  rule: "#e7dfda"
  rule-dark: "#322a29"
  rule-muted: "#f1ebe7"
  rule-muted-dark: "#261f1e"
  rule-emphasized: "#d6ccc7"
  rule-emphasized-dark: "#463c3a"
  logo-ink: "#373435"
  logo-cream: "#f7f1ee"
  error-text: "#991919"
  error-text-dark: "#fca5a5"
  success-text: "#29664f"
  success-text-dark: "#9fd8c3"
  warning-text: "#92310a"
  warning-text-dark: "#fdba74"
  danger-fill: "#dc2626"
  warning-fill: "#92310a"
typography:
  body:
    fontFamily: "SN Pro, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "SN Pro, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  mono:
    fontFamily: "SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace"
    fontSize: "0.875rem"
rounded:
  xs: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "6": "24px"
  "10": "40px"
  "16": "64px"
components:
  button-primary:
    backgroundColor: "{colors.toscana-coral}"
    textColor: "{colors.coral-ink}"
    rounded: "{rounded.sm}"
    height: "40px"
  button-outline:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: "32px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: "40px"
  button-danger-outline:
    backgroundColor: "transparent"
    textColor: "{colors.error-text}"
    rounded: "{rounded.sm}"
    height: "32px"
  badge-audience:
    backgroundColor: "{colors.coral-wash}"
    textColor: "{colors.coral-text}"
    rounded: "{rounded.xs}"
    typography: "{typography.label}"
  badge-tag:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.xs}"
  tab-active:
    textColor: "{colors.coral-text}"
    typography: "{typography.label}"
    height: "44px"
  tab-idle:
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    height: "44px"
---

<!-- Recorded from the shipped build on 2026-11-01. The system is Chakra UI v3 plus the Toscana brand palette (coral, peach, sage, teal) and the official logo. Extend it consistently rather than inventing a parallel look. -->

# Design System: Toscana Pastry

## Overview

**Creative North Star: "The Shop Ledger"**

Toscana Pastry is the shop's ledger: prices, stock, orders, and budgets kept in one honest book. The interface exists to make numbers trustworthy and easy to scan. Tables, clear labels, and plain-sans text carry the work. Ornament stays out of the way of the figures.

The system is Chakra UI v3 plus the Toscana brand palette. The brand has an official logo (a rosette with the "Toscana" lettering, optionally with the tagline "Horneando momentos") and four brand colors: coral #ff7078, peach #f5ccad, sage #cce0c9, and teal #75bda3. The `brand` scale is built around coral. There is no product imagery. The typeface is SN Pro. Light and dark modes: white panels on a warm flour-paper #fbf8f6 canvas in light, stepped cocoa near-black surfaces in dark. Mode follows the OS until the user toggles it in the navbar (next-themes, `dark` class on `<html>`). The admin side is a desktop work surface; the customer portal is a mobile path entered from a WhatsApp link.

The confirmed intent for components is **warm and approachable**: friendlier corners and more breathing room than the current defaults, especially on customer-facing screens. The current code does not yet deliver that; new work should move toward it without breaking the ledger's clarity.

**Key Characteristics:**
- Chakra UI v3 plus the Toscana brand palette; single action accent (coral `brand`), warm neutrals.
- Official logo rendered through `BrandLogo`, ink in light mode and cream in dark.
- Light and dark modes via Chakra semantic tokens; thin warm rules in both.
- Tables are the primary data surface (catalog, orders, ingredients).
- Active state never relies on color alone (bold weight + underline), per WCAG 2.1 AA.
- Toasts via `goey-toast`, Spanish (es-AR) copy, es-AR number formatting.

## Colors

One coral action accent over warm neutrals; peach is its wash, teal and sage carry positive state. Every role has a composed light and dark value: dark is designed, not inverted. Source of truth: semantic tokens in `frontend/src/components/ui/theme.ts`; `theme.test.ts` pins every text pair below to WCAG AA (4.5:1) in both modes.

### Primary
| Role (token) | Light | Dark | Use |
|---|---|---|---|
| **Toscana Coral** fill (`brand.solid`, `toscana.coral`) | #ff7078 | #ff7078 | Primary buttons, active tab underline. The exact brand coral in both modes. |
| Coral ink (`brand.contrast`) | #2a1215 | #2a1215 | Text on coral fills: 6.56:1. White on coral is 2.6:1 and fails. |
| Coral text (`brand.fg`) | #9c1d2a | #ffa4a9 | Active tab, links, spinners. Headings use default `fg`. |
| Coral wash (`brand.subtle`) | #fff4f4 | #470a11 | Subtle badges (audience, role). |
| **Toscana Peach** wash (`brand.muted`, `toscana.peach`) | #f5ccad | #821d29 | Hover and selected washes. Dark mode uses a deep coral in peach's place. |
| Coral emphasized (`brand.emphasized`) | #ffccce | #9c1d2a | Stronger washes (pressed, subtle-variant hover). |
| Focus ring (`brand.focusRing`) | #f74a55 | #ff7078 | Keyboard focus. |

The `brand` scale runs 50 #fff4f4, 100 #ffe4e5, 200 #ffccce, 300 #ffa4a9, 400 coral #ff7078, 500 #f74a55, 600 #e02d3b, 700 #bc1f2e, 800 #9c1d2a, 900 #821d29, 950 #470a11.

### Positive: Teal and Sage
`theme.ts` overrides the `green` palette's semantic keys so positive state speaks in the brand teal and sage.

| Role (token) | Light | Dark | Use |
|---|---|---|---|
| **Toscana Teal** fill (`green.solid`, `toscana.teal`) | #75bda3 | #75bda3 | Solid success tags. Text on it is dark ink `green.contrast` #10251d, never white. |
| Success text (`green.fg`, `fg.success`) | #29664f | #9fd8c3 | Positive values, confirmations. |
| **Toscana Sage** wash (`green.muted`, `toscana.sage`) | #cce0c9 | #183128 | Positive hover and selected washes. |
| Sage subtle (`green.subtle`) | #eef6ec | #0f201a | Subtle success badges. |
| Sage emphasized (`green.emphasized`) | #b3d3ae | #21443a | Stronger positive washes. |

### Neutral
| Role (token) | Light | Dark | Use |
|---|---|---|---|
| **Canvas** (`bg`) | #fbf8f6 | #110e0e | Page and navbar. Light is warm flour paper; dark is cocoa near-black, never pure black. |
| Subtle surface (`bg.subtle`) | #f6f1ee | #161212 | Quiet bands, table zebra. |
| **Panel** (`bg.panel`) | #ffffff | #1b1616 | Cards, forms, dialogs: lifted one step above the canvas. |
| Muted surface (`bg.muted`) | #f1ebe7 | #231d1c | Table headers, neutral chips. |
| Emphasized surface (`bg.emphasized`) | #e7dfda | #2f2826 | Pressed and inactive step markers. |
| **Ink** (`fg`) | #1c1718 | #f7f1ee | Body text and headings. |
| Muted ink (`fg.muted`) | #5e5553 | #b0a5a2 | Secondary text, idle tabs, units. |
| Subtle ink (`fg.subtle`) | #7d7371 | #807573 | Placeholders and disabled only; never body copy. |
| Rule (`border`) | #e7dfda | #322a29 | Default borders and inputs. |
| Muted rule (`border.muted`) | #f1ebe7 | #261f1e | Row separators, quiet dividers. |
| Subtle rule (`border.subtle`) | #f6f1ee | #1d1817 | Faintest dividers. |
| Emphasized rule (`border.emphasized`) | #d6ccc7 | #463c3a | Hovered inputs. |

The logo itself is drawn in a single ink, #373435, and rendered in cream #f7f1ee on dark surfaces (see Components > Logo); these are asset colors, not UI tokens.

### Semantic
| Role (token) | Light | Dark | Use |
|---|---|---|---|
| Error text (`fg.error`, `red.fg`) | #991919 | #fca5a5 | Error messages, negative values. |
| Warning text (`fg.warning`, `orange.fg`) | #92310a | #fdba74 | Warnings. |
| Danger fill (`red.solid`) | #dc2626 | #dc2626 | Destructive buttons (`colorPalette="red"`). |
| Warning fill (`orange.solid`) | #92310a | #92310a | Solid warning tags. |

### Named Rules
**The One Accent Rule.** Coral `brand` is the only action accent. Peach is its wash, never a second accent. Teal and sage carry positive state only (through the `green` palette), never actions or decoration. Status colors (red, green, orange) mean state, never decoration.

**The Semantic Token Rule.** Use semantic tokens (`bg`, `bg.panel`, `fg`, `fg.muted`, `border`, `<palette>.fg`, `<palette>.solid`) and never raw shades (`gray.200`, `brand.600`, hex). Raw shades do not switch with the mode.

**The Role-Not-Default Rule.** Every `<Button>` declares its role: `colorPalette="brand"` (primary), `variant="outline"` (secondary), `variant="ghost"` (tertiary/nav) or `colorPalette="red"` (destructive). A bare `<Button>` falls back to Chakra's gray solid, which renders white in dark mode.

## Typography

**Body Font:** SN Pro (variable, 200–900), with the system sans as fallback. Loaded by `next/font/google` in `app/layout.tsx` as `--font-sn-pro` and wired into Chakra's `fonts.body` and `fonts.heading` tokens in `theme.ts`.
**Mono Font:** Chakra default mono stack.

**Character:** Soft, rounded geometric sans; friendly without losing legibility in dense tables. Fits the warm-and-approachable component direction.

### Hierarchy
- **Brand mark:** the official logo image, never set as text (see Components > Logo).
- **Body** (400, 1rem, 1.5): table cells, form text, descriptions.
- **Label** (400, or 700 when active; 0.875rem): tabs, badges, small buttons, table headers.

### Named Rules
**The Weight-Means-State Rule.** Bold in navigation marks the current page. Don't use bold for decoration in nav.

## Layout

Single column inside Chakra `Container` (`maxW="container.xl"`). The sticky top navbar (z 50) is padded 16px × 12px. Portal pages add a second header with a tab bar (Inicio · Mis pedidos · Carrito · Cuenta) and a "Nuevo pedido" CTA, wrapping on narrow screens. Admin pages use an underline sub-nav (Usuarios · Ingredientes · Configuración) that scrolls horizontally on small widths.

Spacing follows Chakra's 4px scale. Common steps: 4, 8, 12, 16, 24, 40, 64px. Vertical rhythm inside screens is `gap={4}` (16px). Interactive targets in the portal are at least 44px tall.

## Elevation & Depth

Flat. Depth comes from 1px warm rules (`border`) and striped table rows, not shadows. Chakra's default shadows appear only inside overlay components (menus, dialogs, toasts).

**The Flat Ledger Rule.** Surfaces sit flat on the page. Separate regions with a rule or spacing, not a shadow.

## Shapes

Chakra default radii: small corners (4–6px) on buttons, inputs, and table scroll areas; 2px on badges. Tabs are square with a 2px bottom underline. The confirmed "warm and approachable" direction calls for softer corners (8px and up) on customer-facing cards and buttons. That is a direction, not current fact.

## Components

### Buttons
- **Shape:** gently rounded (4px, Chakra `l2`).
- **Primary:** `colorPalette="brand"` solid: coral fill, dark ink text (`brand.contrast`). Sizes `md` (40px) for page CTAs and `sm` (32px) for toolbar actions (export CSV).
- **Outline:** white with gray border, used as secondary next to a primary (export PDF).
- **Ghost:** navbar links (Productos, Administración, Ajustes, Cuenta).
- **Danger outline:** red outline `sm` for "Cerrar sesión".
- **Palette tokens:** `theme.ts` defines the semantic keys Chakra v3 `colorPalette` recipes read: `brand.solid` (400, coral, both modes), `brand.contrast` (#2a1215), `brand.fg` (800 light / 300 dark), `brand.muted` (peach light / 900 dark), `brand.subtle` (50 / 950), `brand.emphasized` (200 / 800), `brand.focusRing` (500 / 400). The fill stays the exact brand coral, so its text is dark ink: white on coral is 2.6:1 and fails WCAG AA.

### Badges
- **Audience / role:** subtle `brand` badge. Admin role uses `red`.
- **Restriction tags** (gluten-free, etc.): subtle `gray` badges under the product name.

### Tables
- Chakra `Table` `size="sm"`, `variant="outline"`, `striped`, inside `Table.ScrollArea` with 6px corners. Prices are right-aligned and formatted es-AR with two decimals. Headers for icon-only columns use `srOnly` text.

### Navigation
- **Navbar:** sticky, canvas (`bg`), bottom rule, horizontal logo (36px, links home) + role badge on the left, ghost links on the right.
- **Tabs (portal and admin):** real links with `aria-current="page"`. Active = coral text (`brand.fg`) + bold + 2px coral underline (`brand.solid`); idle = muted ink, transparent underline. Minimum height is 44px in the portal.

### Logo
- **Component:** `BrandLogo` (`frontend/src/components/layout/BrandLogo.tsx`), props `variant="horizontal" | "vertical"` and `height` in px. It renders both tints and swaps them with Chakra `_dark`: ink (#373435) on light surfaces, cream (#f7f1ee) on dark.
- **Horizontal:** rosette + "Toscana". Navbar, 36px tall.
- **Vertical tagline lockup:** rosette + "Toscana" + "Horneando momentos". Login page, 150px tall, centered above the card.
- **Assets:** sources are `docs/images/*.svg` (single ink #373435). `frontend/scripts/build_brand_assets.mjs` rasterizes them with sharp into `frontend/public/brand/`: `logo_horizontal_{ink,cream}.webp` (108px tall) and `logo_vertical_tagline_{ink,cream}.webp` (660px wide). The favicon is `frontend/src/app/icon.png`, the rosette on peach.

### Feedback
- **Toasts:** `goey-toast` (`gooeyToast.success` / `.error`) with exclamatory es-AR titles ("¡Agregado al carrito!", "¡Ups! …") and a description line.
- **Loading:** centered Chakra `Spinner` `xl`.
- **Empty state:** muted text in a bordered box with 6px corners and 40px vertical padding.

## Do's and Don'ts

### Do:
- **Do** use `colorPalette="brand"` for the single primary action of a view, and outline for its secondary.
- **Do** use Chakra semantic tokens (`bg`, `fg.muted`, `border.muted`) for neutrals.
- **Do** color status text with `red.fg`, `green.fg`, `orange.fg`, or the `fg.error` / `fg.success` / `fg.warning` aliases `theme.ts` remaps to them. Chakra's default `fg.*` status values are 500/600 in light mode and fail 4.5:1 on white.
- **Do** prefer `variant="subtle"` (sage) for green status badges and tags; a solid green tag is teal with dark ink (`green.contrast`), never white text.
- **Do** mark the active nav item with weight + underline + `aria-current`, never color alone.
- **Do** keep portal touch targets at least 44px tall.
- **Do** right-align prices and format them `toLocaleString("es-AR", { minimumFractionDigits: 2 })`.
- **Do** put theme changes in `frontend/src/components/ui/theme.ts`, not inline hex values.
- **Do** show the brand through `BrandLogo`. Never re-tint or recolor the logo beyond its ink and cream assets, and never set the logo as text.

### Don't:
- **Don't** add a second accent color or decorative gradients; peach, sage, and teal are washes and state colors, not accents.
- **Don't** separate surfaces with shadows; use 1px rules.
- **Don't** invent mascots or product photos; none exist (see PRODUCT.md). The official logo is the only brand mark.
- **Don't** set `fontFamily` inline; type comes from Chakra's `fonts.body` / `fonts.heading` tokens (SN Pro).

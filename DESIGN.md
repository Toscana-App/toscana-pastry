---
name: Toscana Pastry
description: Provisional design system for the Toscana Pastry shop tool (admin + customer portal), built on Chakra UI v3 defaults.
colors:
  brand-indigo: "#4f46e5"
  brand-indigo-bright: "#6366f1"
  brand-indigo-wash: "#eef2ff"
  brand-indigo-deep: "#3730a3"
  ink: "#000000"
  ink-muted: "#52525b"
  ink-subtle: "#a1a1aa"
  paper: "#ffffff"
  paper-subtle: "#fafafa"
  paper-muted: "#f4f4f5"
  rule: "#e4e4e7"
  rule-muted: "#f4f4f5"
  alert-red: "#dc2626"
  alert-red-wash: "#fef2f2"
typography:
  wordmark:
    fontFamily: "SN Pro, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
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
    backgroundColor: "{colors.brand-indigo}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    height: "40px"
  button-outline:
    backgroundColor: "{colors.paper}"
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
    textColor: "{colors.alert-red}"
    rounded: "{rounded.sm}"
    height: "32px"
  badge-audience:
    backgroundColor: "{colors.brand-indigo-wash}"
    textColor: "{colors.brand-indigo-deep}"
    rounded: "{rounded.xs}"
    typography: "{typography.label}"
  badge-tag:
    backgroundColor: "{colors.paper-muted}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.xs}"
  tab-active:
    textColor: "{colors.brand-indigo}"
    typography: "{typography.label}"
    height: "44px"
  tab-idle:
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    height: "44px"
---

<!-- PROVISIONAL: recorded as-is on 2026-10-31. The incumbent system is Chakra UI v3 defaults plus an unmodified Tailwind indigo scale; it carries no pastry-shop identity yet. A future /impeccable new-work pass is expected to replace it. Until then, extend it consistently rather than inventing a parallel look. -->

# Design System: Toscana Pastry

## Overview

**Creative North Star: "The Shop Ledger"**

Toscana Pastry is the shop's ledger: prices, stock, orders, and budgets kept in one honest book. The interface exists to make numbers trustworthy and easy to scan. Tables, clear labels, and plain-sans text carry the work. Ornament stays out of the way of the figures.

Today the system is provisional. It is Chakra UI v3's default theme with one custom color scale (`brand`, an unmodified copy of Tailwind's indigo). There is no logo and no product imagery. The typeface is SN Pro. Layout is light-mode only, on white paper with zinc-gray rules. The admin side is a desktop work surface; the customer portal is a mobile path entered from a WhatsApp link.

The confirmed intent for components is **warm and approachable**: friendlier corners and more breathing room than the current defaults, especially on customer-facing screens. The current code does not yet deliver that; new work should move toward it without breaking the ledger's clarity.

**Key Characteristics:**
- Chakra UI v3 defaults; single accent (indigo `brand`), zinc neutrals.
- Light mode only; white background, thin gray rules.
- Tables are the primary data surface (catalog, orders, ingredients).
- Active state never relies on color alone (bold weight + underline), per WCAG 2.1 AA.
- Toasts via `goey-toast`, Spanish (es-AR) copy, es-AR number formatting.

## Colors

One borrowed accent on white paper and zinc neutrals; functional, not yet branded.

### Primary
- **Ledger Indigo** (#4f46e5): wordmark, active tab text and underline in admin nav, primary buttons (`colorPalette="brand"`).
- **Bright Indigo** (#6366f1): active tab underline in the portal tab bar.
- **Indigo Wash** (#eef2ff) / **Deep Indigo** (#3730a3): subtle badge pair, such as the audience badge ("Revendedores" / "Consumidor final") and role badge.

### Neutral
- **Ink** (#000000): default text (Chakra `fg`).
- **Muted Ink** (#52525b): idle tabs, secondary text, empty-state copy (`fg.muted`).
- **Subtle Ink** (#a1a1aa): tertiary text (`fg.subtle`).
- **Paper** (#ffffff): page and navbar background (`bg`).
- **Paper Subtle / Muted** (#fafafa / #f4f4f5): striped table rows, tag badges.
- **Rule** (#e4e4e7): navbar bottom border and default borders (`border`).
- **Rule Muted** (#f4f4f5): portal header border and empty-state boxes (`border.muted`).

### Semantic
- **Alert Red** (#dc2626) / **Red Wash** (#fef2f2): logout button, admin role badge, errors.

### Named Rules
**The One Accent Rule.** Indigo `brand` is the only accent. Status colors (red, green, orange) mean state, never decoration.

**The Semantic Token Rule.** Use Chakra semantic tokens (`bg`, `fg`, `fg.muted`, `border`, `border.muted`) for neutrals, not raw `gray.*` values, so a future theme swap lands in one file (`frontend/src/components/ui/theme.ts`).

## Typography

**Body Font:** SN Pro (variable, 200–900), with the system sans as fallback. Loaded by `next/font/google` in `app/layout.tsx` as `--font-sn-pro` and wired into Chakra's `fonts.body` and `fonts.heading` tokens in `theme.ts`.
**Mono Font:** Chakra default mono stack.

**Character:** Soft, rounded geometric sans; friendly without losing legibility in dense tables. Fits the warm-and-approachable component direction.

### Hierarchy
- **Wordmark** (700, 1.25rem): "Toscana Pastry" text in the navbar, Ledger Indigo.
- **Body** (400, 1rem, 1.5): table cells, form text, descriptions.
- **Label** (400, or 700 when active; 0.875rem): tabs, badges, small buttons, table headers.

### Named Rules
**The Weight-Means-State Rule.** Bold in navigation marks the current page. Don't use bold for decoration in nav.

## Layout

Single column inside Chakra `Container` (`maxW="container.xl"`). The sticky top navbar (z 50) is padded 16px × 12px. Portal pages add a second header with a tab bar (Inicio · Mis pedidos · Carrito · Cuenta) and a "Nuevo pedido" CTA, wrapping on narrow screens. Admin pages use an underline sub-nav (Usuarios · Ingredientes · Configuración) that scrolls horizontally on small widths.

Spacing follows Chakra's 4px scale. Common steps: 4, 8, 12, 16, 24, 40, 64px. Vertical rhythm inside screens is `gap={4}` (16px). Interactive targets in the portal are at least 44px tall.

## Elevation & Depth

Flat. Depth comes from 1px gray rules and striped table rows, not shadows. Chakra's default shadows appear only inside overlay components (menus, dialogs, toasts).

**The Flat Ledger Rule.** Surfaces sit flat on the page. Separate regions with a rule or spacing, not a shadow.

## Shapes

Chakra default radii: small corners (4–6px) on buttons, inputs, and table scroll areas; 2px on badges. Tabs are square with a 2px bottom underline. The confirmed "warm and approachable" direction calls for softer corners (8px and up) on customer-facing cards and buttons. That is a direction, not current fact.

## Components

### Buttons
- **Shape:** gently rounded (4px, Chakra `l2`).
- **Primary:** `colorPalette="brand"` solid, white text. Sizes `md` (40px) for page CTAs and `sm` (32px) for toolbar actions (export CSV).
- **Outline:** white with gray border, used as secondary next to a primary (export PDF).
- **Ghost:** navbar links (Productos, Administración, Ajustes, Cuenta).
- **Danger outline:** red outline `sm` for "Cerrar sesión".
- **Palette tokens:** `theme.ts` defines the semantic keys Chakra v3 `colorPalette` recipes read: `brand.solid` (600), `brand.contrast` (white), `brand.fg` (700), `brand.muted` (100), `brand.subtle` (50), `brand.emphasized` (200), `brand.focusRing` (500). Solid is 600, not 500, because white on 500 is 4.47:1 and fails WCAG AA.

### Badges
- **Audience / role:** subtle `brand` badge. Admin role uses `red`.
- **Restriction tags** (gluten-free, etc.): subtle `gray` badges under the product name.

### Tables
- Chakra `Table` `size="sm"`, `variant="outline"`, `striped`, inside `Table.ScrollArea` with 6px corners. Prices are right-aligned and formatted es-AR with two decimals. Headers for icon-only columns use `srOnly` text.

### Navigation
- **Navbar:** sticky, white, bottom rule, wordmark + role badge on the left, ghost links on the right.
- **Tabs (portal and admin):** real links with `aria-current="page"`. Active = indigo text + bold + 2px indigo underline; idle = muted ink, transparent underline. Minimum height is 44px in the portal.

### Feedback
- **Toasts:** `goey-toast` (`gooeyToast.success` / `.error`) with exclamatory es-AR titles ("¡Agregado al carrito!", "¡Ups! …") and a description line.
- **Loading:** centered Chakra `Spinner` `xl`.
- **Empty state:** muted text in a bordered box with 6px corners and 40px vertical padding.

## Do's and Don'ts

### Do:
- **Do** use `colorPalette="brand"` for the single primary action of a view, and outline for its secondary.
- **Do** use Chakra semantic tokens (`bg`, `fg.muted`, `border.muted`) for neutrals.
- **Do** mark the active nav item with weight + underline + `aria-current`, never color alone.
- **Do** keep portal touch targets at least 44px tall.
- **Do** right-align prices and format them `toLocaleString("es-AR", { minimumFractionDigits: 2 })`.
- **Do** put theme changes in `frontend/src/components/ui/theme.ts`, not inline hex values.

### Don't:
- **Don't** add a second accent color or decorative gradients; the One Accent Rule holds until a redesign.
- **Don't** separate surfaces with shadows; use 1px rules.
- **Don't** invent a logo, mascot, or product photos; none exist (see PRODUCT.md).
- **Don't** set `fontFamily` inline; type comes from Chakra's `fonts.body` / `fonts.heading` tokens (SN Pro).

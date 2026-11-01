# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Installable as a PWA (architecture decision #7). Mobile web, not a native app.

## Users

- **Administrator (the owner):** the single owner of one local pastry shop and the only admin. Works mostly on desktop. Manages catalog, pricing, ingredient stock, users, orders, budgets, and sales closing. The role is exclusive and never delegated.
- **Businesses (resellers):** health-food stores, kiosks, and other resellers. Use the app mostly on mobile, often arriving from a WhatsApp link. See the catalog with reseller prices and manage their own orders (create, status, tracking).
- **Private customers (end consumers):** use the app mostly on mobile, often arriving from a WhatsApp link. See the catalog with end-consumer prices, create or receive budgets with PDF, and manage their own orders.

## Product Purpose

Let one pastry shop run the full cycle (price, stock, order, budget, delivery) inside its own tool instead of a generic external service, spreadsheets, and memory. Success means: prices derive themselves from ingredients, stock is never negative or corrupted, budgets go out as a ready PDF over WhatsApp, and each customer type only ever sees its own price list.

## Positioning

A single-tenant tool built around this shop's real flow, not a generic pastry SaaS. Its mechanisms: prices derived from ingredients on every read (never persisted), atomic stock deduction on order confirmation, budget→order flow with PDF + WhatsApp as the real sales channel, and two strictly separated price lists (reseller vs end consumer) enforced by a three-role system in the backend.

Multi-tenant or SaaS is out of scope for v1; it is considered only if demand appears (v1.x). Older docs (README, AGENTS.md) still say "SaaS para reposteras"; the PRD is the authority.

## Operating Context

- WhatsApp is the real sales channel: budgets are sent as PDF over WhatsApp and approval happens in the same thread. Customers often enter the app from a WhatsApp link.
- Admin works at a desktop: catalog, cost calculator, ingredients with traceable movements (purchase / waste / adjustment), settings, users.
- Customer portal: catalog, cart, checkout (Mercado Pago payment), my orders, profile.
- Money is shown in Argentine pesos, es-AR formatting.

## Capabilities and Constraints

- Three roles: `admin`, `negocio`, `cliente`. Out-of-role access returns 403; frontend routes are protected. A reseller never receives end-consumer prices and an end consumer never receives reseller prices. Cross-visibility of price lists is a non-goal by design.
- Dual pricing: end-consumer price = reseller price × markup (default +40%), configurable from the admin panel as a tenant setting, never stored on products. Price list exportable as CSV and PDF per audience, gated by role.
- Product form recalculates price live via `POST /pricing/preview` (no client-side pricing mirror).
- Order confirmation deducts stock atomically; on shortage the API answers 409 `insufficient_stock` with available and missing quantities.
- Budgets: client with phone (no email), totals with 21% IVA, PDF, "Send via WhatsApp".
- Pending spec items (23/10): allergen/restriction tags on products, order window, payment status, delivery address, weekly summary + CSV export, Google Sign-In privacy.
- Money is integer cents end to end; `Pct` and `Qty` are strings.
- Not in v1: multi-tenant, SaaS, invoicing, native app, admin delegation, inbound WhatsApp Business API (open decision).
- Full business detail: `docs/PRD-toscana-pastry.md`; screen specs in `docs/specs/`.

## Brand Commitments

No logo, name treatment, or visual identity exists yet. Do not invent a logo or brand mark.

Observed copy convention in shipped UI (not yet confirmed as a binding brand voice): Spanish (Argentina) with "tú" address (tuteo), es-AR price format.

## Evidence on Hand

- Product docs: `docs/PRD-toscana-pastry.md`, `docs/specs/`.
- UI screenshots: `docs/screenshots*`.
- No real product photos, testimonials, customer quotes, or metrics exist. Do not fabricate them. No baseline conversion rate is measured.

## Product Principles

1. Each role sees exactly its own scope; a price leak between lists is a critical failure, not a cosmetic one.
2. Numbers must be trustworthy: derived prices, atomic stock, cents-exact money. The UI never shows a price it did not get from the backend.
3. WhatsApp is the channel; the app supports the conversation instead of replacing it.
4. Admin is a desktop work tool; the customer side is a fast mobile path from a WhatsApp link to an order.
5. Build for this one shop's real flow before any generalization.

## Accessibility & Inclusion

WCAG 2.1 AA, enforced with automated accessibility tests (vitest + axe) on customer-facing screens such as the cart.

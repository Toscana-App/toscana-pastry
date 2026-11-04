# Spec gap closure (toscana-pastry)

Auditoría spec → código sobre `origin/main` `74ce7a2` (2026-11-03). Cruza `docs/specs/p01`–`p11` + `master_plan` contra el código real (routers backend, módulos frontend). Conclusión: el núcleo de las fases 2–5, 7–9 y el portal F1–F4 están implementados; **las fases faltantes son: Fase 1 (auth) casi toda, los remanentes de alignment T1/T2/T7/T9/T10–T13 (nunca llegaron a main), el hardening de Fase 4 (CI/RLS/PWA), los gaps P11 del portal y la Fase 10 inbound de WhatsApp**.

Nota de contexto: los commits citados en `spec-alignment-phases1-8.md` (T2 order-window, T7 weekly/export, T10 budgets export, T12 PDF/WhatsApp) **no existen en ninguna rama remota** — las branches `feat/phase*` están 100% mergeadas sin ese trabajo. Se reimplementan desde la spec, no se recuperan.

## Fases vs estado (origin/main)

| Fase | Spec | Estado |
|---|---|---|
| 0 — Base | Fase 0 | Parcial: falta `manifest.json`, service worker, `not-found.tsx` (404), `sitemap.xml`, `robots.txt` |
| 1 — Auth | p01 | **Faltante**: login es email directo (dev); sin magic link, sin token de compra, sin Google GIS, sin cookies httpOnly, sin onboarding, sin rate limit |
| 2 — Ingredientes | p02 | ✅ CRUD, stock, import, historial inmutable |
| 3 — Productos | p03 | Parcial: falta `tags[]` (RF-P4-01, RF-P3-07/08) |
| 4 — Precios/Settings | p04/p05 | ✅ núcleo (motor Decimal, 13 campos, preview, dual pricing + markup). Falta hardening (CI, RLS, PWA) |
| 5 — Pedidos admin | p06 | Parcial: falta API/UI order-window (RF-P5-07), banner de corte admin (RF-P6-09), UI "Sin pagar" (RF-P6-10), resumen semanal + export (RF-P6-11). Backend de paid ✅ |
| 7 — Wizard presupuestos | p07 | Parcial: falta dirección de entrega, tags, sugerencia de cliente duplicado (RF-P7-03) y libro de direcciones (RF-P11-09) |
| 8 — Presupuestos | p08/p09 | Parcial: backend ✅ (versión, congelado, PDF, link, límite 30/día, enmascarado). Falta frontend Fase 8 (preview PDF, botón WhatsApp, estado expirado) |
| 9 — PDF | p09 | ✅ backend (pdf, share token, link público) |
| 10 — WhatsApp | p10 | Outbound ✅ backend (sends, stats, resend). **Faltante**: webhook inbound (RF-P10-03..05), Chat SDK (RF-P10-10), UI de envíos (RF-P10-08) |
| Portal F1–F4 | p11 | ✅ (home, catálogo, carrito, checkout, consent, GA4 consent, 409 corte, MercadoPago). Gaps: Idempotency-Key en POST /orders (RF-P11-02), eventos GA4 e-commerce (RF-P11-15) |

Bug de contrato detectado: el frontend llama `POST /orders/{id}/whatsapp` (`frontend/src/services/ordersService.ts:88`) pero el backend expone `POST /orders/{order_id}/whatsapp-link` → el botón WhatsApp de pedidos falla (404/405).

## Specs

S1 — **Tags de producto** (spec-alignment S1; p03 RF-P3-07/08, p04 RF-P4-01): `tags[]` 0–10 (≤30 chars, allow-list sugerida: sin gluten, sin lácteos, sin azúcar, sin lactosa, frutos secos, vegano + free text); `GET /products/tags` → `[{name,count}]`; filtro `tags` (AND) combinable con categoría; card muestra máx. 2 + "+n".

S2 — **Order window** (spec-alignment S2/S3/S4; p05 RF-P5-07, p06 RF-P6-09): `GET/PATCH /api/v1/tenant/order-window` → `{open, reopens_at?, message?}`; cerrar sin `reopens_at` → 422 con sugerencia; `message` ≤ 200. UI settings: toggle + datetime + mensaje. UI Pedidos: banner `Alert.Root` warning con mensaje + reapertura, CTA de creación deshabilitado. GA4: `order_window_changed`. El 409 `order_window_closed` de `POST /orders` (portal) ya existe (verificado `orders/router.py` create_order_portal).

S3 — **Paid UI** (spec-alignment S5; p06 RF-P6-10): filtro "Sin pagar" + contador en header de lista; badge `Pagado`/`Sin pagar` (texto, no solo color); toggle que marca pagado sin tocar estado de entrega. Backend ya existe: `PATCH /orders/{id}/paid` (monotónico, admin), filtro `paid` en listado.

S4 — **Weekly + export** (spec-alignment S6; p06 RF-P6-11): `GET /orders/weekly?week?` → `{week:{from,to}, items, totals:{amount,paid,unpaid}}` (semana natural Lun–Dom, pedidos confirmado/entregado); `GET /orders/export?from,to,status,paid` → `text/csv` streaming (id, cliente, fecha, ítems, total, estado, pago); `GET /budgets/export` → CSV (seq, cliente, fecha, entrega, total venta, estado). UI: vista resumen semanal + CTAs export en Pedidos y Presupuestos.

S5 — **Presupuestos: dirección, tags y dedupe** (spec-alignment S7/T8/T10/T11/T12 + p07 RF-P7-03, p08, p09 RF-P9-01, p10 RF-P10-01, p11 RF-P11-09):
- `delivery_address?` en customers (`POST/PATCH /customers`) y en creación de presupuesto (customer inline o reuso).
- Snapshot de `tags[]` del producto en budget items (congelado, como el precio).
- PDF y mensaje de WhatsApp: entrega (fecha + dirección si presente) y tags de restricción por ítem si existen.
- Wizard paso 1: campo dirección de entrega opcional + sugerencia de cliente duplicado (match por teléfono/email, opción "Usar datos existentes"); sugerencia desde el libro de direcciones (C2 `/me/addresses` ya existe).
- Paso 2: chips de tags (filtro). Paso 3: resumen con dirección + tags por ítem.

S6 — **Fase 8 frontend** (spec-alignment S8/T13; p09 RF-P9-05/06, p10 UI): preview del PDF (`GET /budgets/{id}/pdf`) + botón "Enviar por WhatsApp" (wa.me link, registro de envío) + estado expirado del link público. Incluye fix del bug de contrato `POST /orders/{id}/whatsapp` → `/whatsapp-link`.

S7 — **Auth p01** (p01 RF-P1-01..12, RNF-P1-03): magic link (email → token con TTL, resend, login sin contraseña); token de compra (RF-P1-02); sesión en cookies `httpOnly`+`Secure`+`SameSite=Strict` (hoy: `document.cookie` JS, `SameSite=Lax`); Google GIS (RF-P1-08..12: `GET /auth/google` con nonce, `GET /auth/google/callback`, 400 si no hay nonce en sesión, email verificado); onboarding de tenant al primer login (RF-P1-05); rate limit en login.

S8 — **Hardening Fase 4** (RNF-P4-01..04, Fase 0): CI (lint + typecheck + test en PR, `RNF-P4-01`); RLS en Postgres (`RNF-P4-03`, el app ya corre sobre Postgres por `postgres-test-suite.md`); PWA: `manifest.json` + service worker (Fase 0); `not-found.tsx` (404) (Fase 0); `sitemap.xml` + `robots.txt`; Lighthouse CI (perf ≥ 90, a11y ≥ 95, best practices ≥ 95) + crawler de links rotos + contraste AA.

S9 — **Gaps P11 portal** (p11 RF-P11-02, RF-P11-15): `Idempotency-Key` requerido en `POST /orders` (hoy solo en `POST /orders/{id}/payment`); eventos GA4 e-commerce (hoy solo `order_confirmed` dispara `trackEvent`; faltarían view_catalog/add_to_cart/begin_checkout/purchase según spec).

S10 — **Fase 10 inbound WhatsApp** (p10 RF-P10-03..05, RF-P10-08, RF-P10-10): webhook inbound (recepción de mensajes, persistencia, asignación a presupuesto/pedido); Chat SDK en UI (hilo de conversación); UI de WhatsApp Business (lista de envíos, stats, reenvío). **Bloqueante externo**: requiere verificación del número en WhatsApp Business API — se planifica en paralelo, no frena el resto.

## RF / RNF involucrados (gaps)

- RF-P1-01, RF-P1-02, RF-P1-03 (parcial: cookie JS no httpOnly), RF-P1-05, RF-P1-06, RF-P1-08..12 (S7)
- RNF-P1-03 (S7)
- RF-P3-07, RF-P3-08, RF-P4-01 (S1)
- RF-P5-07 (S2), RF-P6-09 (S2), RF-P6-10 (S3), RF-P6-11 (S4)
- RF-P7-03 (S5), RF-P8-01 (dirección en presupuesto) (S5), RF-P8-13, RF-P8-14 (S6), RF-P9-01 (S5), RF-P9-05, RF-P9-06 (S6), RF-P10-01 (tags/dirección en mensaje) (S5)
- RF-P10-03, RF-P10-04, RF-P10-05, RF-P10-08, RF-P10-10 (S10)
- RF-P11-02 (parcial: solo payment), RF-P11-09 (S5), RF-P11-15 (parcial) (S9)
- RNF-P4-01, RNF-P4-03 (S8)

Fuera de scope (decidido): RF-P9-07 (logo en PDF) — difiere de security #16 (solo datos de la sesión); se mantiene postergado.

## Tasks

Cada task = 1 PR. Base: `origin/main`. Las tareas S1–S6 son el alignment pendiente y son independientes entre sí (excepto S5 backend → S5 frontend y S5 → S6 PDF).

- T1 (branch `feat/tags`, S1): `tags[]` en producto (domain/model/schemas/CRUD, validación 0–10 y ≤30 chars), `GET /products/tags`, filtro `tags` (AND) en `GET /products`. UI: multi-select en tab Información, chips en card (máx. 2 + "+n"), filtro combinable con categoría. Commits: `feat(products): tags de restricción (P3/P4)` + `feat(products): UI de tags`. Status: OPEN. Risk: ninguno (campo opcional, additive).
- T2 (branch `feat/order-window`, S2): `GET/PATCH /api/v1/tenant/order-window` (usa `OrderWindowORM` existente, ya leída por `POST /orders`); 422 al cerrar sin `reopens_at`. UI settings: sección "Corte de pedidos". UI Pedidos: banner + CTA deshabilitado. GA4 `order_window_changed`. Commits: `feat(tenant): order-window (corte de pedidos)` + `feat(settings): corte de pedidos (order-window)` + `feat(orders): banner de corte (P6-09)`. Status: OPEN. Risk: ninguno (409 portal ya consume el mismo estado).
- T3 (branch `feat/paid-ui`, S3): filtro "Sin pagar" + contador, badge/toggle de pago en Pedidos. Consumir `PATCH /orders/{id}/paid` y filtro existente. Commit: `feat(orders): UI estado de pago (P6-10)`. Status: OPEN. Risk: ninguno.
- T4 (branch `feat/weekly-export`, S4): `GET /orders/weekly` + `GET /orders/export` (CSV streaming) + `GET /budgets/export`. UI: vista resumen semanal + CTAs export. Commits: `feat(orders): resumen semanal + export CSV (P6-11)` + `feat(budgets): export CSV` + `feat(orders-fe): resumen semanal + export`. Status: OPEN. Risk: ninguno (read-only).
- T5 (branch `feat/budget-address-tags`, S5 backend): `delivery_address?` en customers y presupuestos; snapshot `tags[]` en budget items; PDF y template de WhatsApp con dirección (si presente) y tags por ítem (si existen). Commits: `feat(customers): delivery_address` / `feat(budgets): delivery_address + tags snapshot` / `feat(budgets): PDF y WhatsApp con dirección y tags`. Status: OPEN. Risk: low (depende de tags de T1 para que el snapshot tenga datos; funciona vacío sin T1).
- T6 (branch `feat/budget-wizard`, S5 frontend + S7): wizard paso 1: dirección opcional + sugerencia de cliente duplicado (teléfono/email) + sugerencia desde libro de direcciones (`/me/addresses`); paso 2: chips de tags; paso 3: dirección + tags por ítem. Commits: `feat(budgets): dirección + dedupe + tags en wizard`. Status: OPEN. Depends on T5, T1.
- T7 (branch `feat/phase8-frontend`, S6): preview PDF + botón "Enviar por WhatsApp" + estado expirado en módulo budgets; fix contrato `POST /orders/{id}/whatsapp` → `/orders/{id}/whatsapp-link`. Commit: `feat(budgets): Fase 8 frontend — preview PDF + envío WhatsApp`. Status: OPEN. Depends on T5.
- T8 (branch `feat/auth-p01`, S7): magic link end-to-end (envío de email con token TTL + resend), token de compra, cookies `httpOnly`+`Secure`+`Strict`, Google GIS (nonce + callback + 400 sin nonce + email verificado), onboarding de tenant, rate limit en login. Commits por sub-capacidad. Status: OPEN. Risk: alto (cambia el auth actual de dev; requiere SMTP real y OAuth client de Google). Pre-requisito de producción.
- T9 (branch `feat/hardening-fase4`, S8): CI (lint/typecheck/test en PR), RLS en Postgres (policies por rol/tenant), `manifest.json` + service worker, `not-found.tsx`, `sitemap.xml` + `robots.txt`, Lighthouse CI + crawler de links rotos. Commits separados por ítem. Status: OPEN. Risk: mediano (RLS puede romper flujos existentes; validar con la suite completa en Postgres).
- T10 (branch `feat/portal-p11`, S9): `Idempotency-Key` en `POST /orders`; eventos GA4 e-commerce faltantes. Commits: `feat(orders): Idempotency-Key en POST /orders` + `feat(analytics): eventos GA4 e-commerce`. Status: OPEN. Risk: low (el header puede ser opt-in con warning si rompería clientes existentes — decidir en el PR).
- T11 (branch `feat/whatsapp-inbound`, S10): webhook inbound + persistencia + Chat SDK + UI WhatsApp Business. Status: OPEN, **bloqueado por verificación externa** (número en WhatsApp Business API). Preparar la rama y el contrato; no frena T1–T10.

## Status

- Baseline: `origin/main` `74ce7a2` (2026-11-01). Auditoría: 2026-11-03.
- Todo OPEN. Sugerencia de orden de delivery: T2 → T3 → T4 → T1 → T5 → T6 → T7 (cierre de alignment, todas low-risk) → T10 → T9 → T8 → T11. El portal y el negocio quedan completos contra spec con T1–T7; T8 es el pre-requisito de producción; T11 depende del número verificado.

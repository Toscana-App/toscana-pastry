# Spec alignment phases 1–8 (toscana-pastry)

Align every executed phase branch (open PRs #9–#16 + missing fase 8 frontend) with the refined specs committed in main `1451740` (elclubdelosaludable recon, 23/10). All phase branches diverged from `5cf9b7d` BEFORE the spec update and are **cumulative** (each contains all prior phases' work). Strategy: implement each gap on its origin branch, rebase downstream cumulative branches onto the updated origin, so every PR is self-contained.

## Specs

S1 — **Product tags** (task #26, docs/specs/p03+p04, api_endpoints):
- RF-P4-01: `tags[]` (0–10; allow-list sugerida de restricciones: sin gluten, sin lácteos, sin azúcar, sin lactosa, frutos secos, vegano, + texto libre ≤ 30 chars).
- RF-P3-07: Filtro por tag (chips secundarios, combinables entre sí y con categoría); tags derivados de los productos existentes.
- RF-P3-08: La card muestra máx. 2 tags + "+n"; el tag completo se ve en el detalle (P4).
- API: `GET /products` (`?q,category,tags,page,page_size`; `tags` = lista (AND); item incluye `tags[]`); `GET /products/tags` → `{tags:[{name,count}]}`; `POST/PATCH /products` con `tags[]?` (0–10, ≤ 30 chars c/u).

S2 — **Order window** (task #27, docs/specs/p05 RF-P5-07, api_endpoints):
- RF-P5-07: `order_window_open` (bool, default true), `order_window_reopens_at` (datetime, requerido si se cierra sin abrir), `order_window_message` (≤ 200 chars). Cerrada → P6 muestra banner con el mensaje y bloquea la creación.
- API: `GET /api/v1/tenant/order-window` → `{open, reopens_at?, message?}` (auth). `PATCH` `{open*, reopens_at?, message?}`; cerrar sin `reopens_at` → 422 con sugerencia; `message` ≤ 200 chars.
- P5 UI: "Cierro los pedidos con fecha de reapertura y un mensaje; en Pedidos (P6) veo el banner y no puedo crear pedidos." (criterio de aceptación p05)

S3 — **Order-window UI settings** (docs/specs/p05, UC-05): "Toggle + fecha de reapertura + mensaje → guardado; el banner aparece en Pedidos (P6)". GA4: `order_window_changed`.

S4 — **Orders cutoff 409 + banner** (docs/specs/p06 RF-P6-09):
- "Corte de pedidos: si `order_window_open=false` (P5) → banner en lista y creación con `order_window_message`; `POST /orders` → 409 `{detail: order_window_closed, message}`."
- P6 UI: "banner de corte (`Alert.Root` warning) cuando `order_window_open=false` (lecto de `/tenant/order-window` en el shell)"; "CTA de creación deshabilitado".

S5 — **Paid state** (task #29, docs/specs/p06 RF-P6-10):
- "Estado de pago: `paid` (bool, server-managed, default false), **independiente** de la máquina de estados de entrega; `PATCH /orders/{id}/paid`; filtro `paid=false` ("Sin pagar") en la lista + contador en el header."
- UI: "badge `Pagado` success / `Sin pagar` warning (texto, no solo color)"; "Marco un pedido como pagado sin tocar su estado de entrega; veo el contador de 'sin pagar'".

S6 — **Weekly summary + CSV export** (task #28, docs/specs/p06 RF-P6-11):
- "Resumen semanal: semana natural (Lun–Dom) con pedidos `confirmado`/`entregado` (cliente, ítems, total, pago), totales (`amount`, `paid`, `unpaid`) + export CSV `GET /orders/export` (y `GET /budgets/export` en F3)."
- API: `GET /orders/weekly` `?week?` → `{week:{from,to}, items, totals:{amount,paid,unpaid}}`; `GET /orders/export` `?from,to,status,paid` → `text/csv`, columnas: id, cliente, fecha, ítems, total, estado, pago. Streaming.
- `GET /budgets/export` → columnas: seq, cliente, fecha, entrega, total venta, estado.
- UI: "Veo el resumen de la semana (pedidos, totales, pagado/pendiente) y exporto a CSV."

S7 — **Delivery address** (task #30, docs/specs/p07+p08+p09+p10):
- p07: "La dirección de entrega es opcional; si está presente aparece en el resumen (P8), en el PDF (P9) y en el mensaje de WhatsApp (P10)."
- API customers: `POST /customers` `{name*, phone?, email?, delivery_address?}`.
- API budgets: `customer:{...}o customer_id (con delivery_address?)`.
- p08: "los datos del cliente (con dirección de entrega, si está presente) y la tabla de ítems … (con tags de restricción por ítem, si existen)".
- p09 RF-P9-01: entrega (fecha + **dirección si está presente**), ítems (con **tags de restricción** por ítem).
- p10 RF-P10-01: ítems (qty × producto — precio, + **tags de restricción** si existen), **dirección de entrega** (si está presente).

S8 — **Fase 8 frontend** (docs/specs/p09 + p10 UI, pendiente PR #17): preview del PDF (`GET /budgets/{id}/pdf`) + botón "Enviar por WhatsApp" (wa.me link, registro de envío). Pattern de las ramas: base main, acumulativa sobre feat/phase7-frontend.

## Tasks

- T1 (p5be, S1): tags en producto domain/model/schemas/CRUD + `GET /products/tags` + filtro `tags` (AND) en listado. Worktree `.worktrees/p5be`, branch `feat/phase5-backend`. Commit: `feat(products): tags de restricción (P3/P4)`.
- T2 (p5be, S2): `GET/PATCH /api/v1/tenant/order-window` (tenant domain + router). 422 cerrar sin reopens_at; message ≤ 200. Commit: `feat(tenant): order-window (corte de pedidos)`.
- T3 (p4fe, S2/S3): sección "Corte de pedidos" en settings: toggle + datetime reapertura + mensaje; manejo gracioso si el endpoint no existe aún (404 → sección deshabilitada con hint). Worktree `.worktrees/p4fe`, branch `feat/phase4-frontend`. Commit: `feat(settings): corte de pedidos (order-window)`.
- T4 (p5fe, S1): multi-select de tags en tab Información (allow-list + free text ≤ 30, máx 10); chips de tags en card (máx 2 + "+n"); filtro por tags combinable con categoría. Worktree `.worktrees/p5fe`, branch `feat/phase5-frontend`. Commit: `feat(products): UI de tags (chips, filtro, multi-select)`.
- T5 (p6be, S4): `POST /orders` → 409 `{detail: order_window_closed, message}` cuando la ventana está cerrada (lee tenant order_window). Worktree `.worktrees/p6be`, branch `feat/phase6-backend`. Commit: `feat(orders): bloquear creación con order_window_closed (P6-09)`.
- T6 (p6be, S5): flag `paid` (default false, server-managed) en order; `PATCH /orders/{id}/paid`; filtro `paid` en listado; `paid` en items. Commit: `feat(orders): estado de pago independiente (P6-10)`.
- T7 (p6be, S6): `GET /orders/weekly` (semana Lun–Dom, confirmado/entregado, totals) + `GET /orders/export` (CSV streaming, filtros from/to/status/paid). Commit: `feat(orders): resumen semanal + export CSV (P6-11)`.
- T8 (p6be, S7): `delivery_address?` en customers (create/patch/list/detail). Commit: `feat(customers): delivery_address`.
- T9 (p6fe, S4/S5/S6): banner de corte en shell/lista (Alert warning, mensaje + reopens_at, CTA creación deshabilitado); filtro "Sin pagar" + contador; badge/toggle de pago (PATCH paid); vista resumen semanal + CTA export CSV. Worktree `.worktrees/p6fe`, branch `feat/phase6-frontend`. Commit: `feat(orders): banner de corte, estado de pago y resumen semanal`.
- T10 (p7be, S6/S7/S1): budgets: `delivery_address?` en creación (customer inline o reuso); snapshot de `tags[]` del producto en budget items; `GET /budgets/export` (CSV: seq, cliente, fecha, entrega, total venta, estado). Worktree `.worktrees/p7be`, branch `feat/phase7-backend`. Commits: `feat(budgets): delivery_address + tags snapshot` / `feat(budgets): export CSV`.
- T11 (p7fe, S6/S7/S1): wizard paso 1: campo dirección de entrega (opcional); paso 2: chips de tags de restricción (filtro); paso 3: resumen con dirección (si presente) + tags por ítem (si existen); listado presupuestos: CTA export CSV. Worktree `.worktrees/p7fe`, branch `feat/phase7-frontend`. Commit: `feat(budgets): dirección de entrega + tags en wizard y resumen`.
- T12 (p8be, S7/S1): PDF: entrega con dirección (si presente) + tags por ítem (si existen); WhatsApp template: tags por ítem + dirección (si presente). Worktree `.worktrees/p8be`, branch `feat/phase8-backend`. Commit: `feat(budgets): PDF y WhatsApp con dirección y tags`.
- T13 (p8fe, S8): crear branch `feat/phase8-frontend` desde `feat/phase7-frontend` (post-T11); PDF preview + botón "Enviar por WhatsApp" en módulo budgets. Base main. Abrir PR #17. Worktree `.worktrees/p8fe`. Commit: `feat(budgets): Fase 8 frontend — preview PDF + envío WhatsApp`.
- T14 (all, —): rebase de ramas acumulativas downstream (p6be←p5be, p7be←p6be, p8be←p7be; p5fe←p4fe, p6fe←p5fe, p7fe←p6fe), re-run de gates por rama, push de todas las ramas.

## Out of scope (documented, no phase 1–8 open PR)

- PWA instalable (task #25): F0/F4 — F0 ya mergeada, F4 sin iniciar.
- Legal Google Sign-In (task #31) y anti-patterns security (task #32): docs ya commitadas en main.
- Decision #7 (sin portal self-service ni sockets): sin código.
- Footgun enum role, SECRET_KEY default, E2E formalización: decisiones abiertas preexistentes, no parte del refine 23/10.

## Log

L1 — User request (verbatim, 2026-10-25): "Tarea: Analiza el siguiente archivo @C:\Users\Usuario\Downloads\toscana-pastry_desarrollo.md que contiene el historial de cambios realizados sobre el proyecto,los pr abiertos y las decisiones tomadas hasta el momento.Tu objetivo sera hacer un sync con este status.Luego,analiza el archivo actual de spec y buscar para cada una de las fases,el pr asociado.Analiza los cambios realizados en el pr y determina cuales son las specs que estan faltando,ya que las specs cambiaron.El objetivo de esta tarea será alinear las fases ya ejecutadas y que se encuentran en pr con las nuevas specs.Tu tarea termina cuando las fases ya ejecutadas se encuentren completas(hasta fase 8).Trabaja sobre las mismas ramas de cada fase.Utiliza para cada fase,ODD como guia para implementar los cambios"

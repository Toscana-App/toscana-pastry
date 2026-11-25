# O5 — Comprobante de transferencia: upload, verificación manual y storage

Objetivo: cerrar el loop del método de pago `transfer` (quedó como S8/T7 pendiente en
O4, PR #88): el cliente del portal sube el comprobante bancario (PDF/JPEG/PNG), el admin
lo valida en el panel con alta prioridad y lo confirma (pago `approved`, pedido avanza a
`preparing`) o lo rechaza (pago `rejected`, pedido `cancelled`). El comprobante vive en
storage del backend (fuera del webroot, sin mount público, solo entrega autenticada), es
único e irrevocable, y puede borrarse recién cuando el pedido llega a `delivered`,
conservando el historial del medio de pago en el pedido.

Branch: `feat/transfer-receipt` (worktree `.worktrees/transferreceipt`), apilada sobre
`feat/payment-methods` (O4, PR #88), que a su vez apila sobre `feat/payment-states` (O2)
y `feat/order-prep-states` (O1). Delivery: `ask-on-risk`. Runner: backend `backend/.venv`
desde la raíz → `python -m pytest -q` desde `backend/`; frontend → `tsc + eslint +
vitest + next build`; e2e → suite `backend/e2e/` (uvicorn real + Postgres real, único
mock: API de MercadoPago) con su playbook.

## Pedido del usuario (verbatim, 2026-11-24)

> 1) a — 2) En la pantalla de congrats del pedido, debe mostrarse una card de info con
> un color de warning que especifique: "Para confirmar su pedido, por favor suba el
> comprobante de la transferencia" y agregar un botón grande que especifique "Subir
> comprobante". Al presionar, debes mostrar un alert dialog con la sección para
> importar/arrastrar un archivo. Las extensiones soportadas son PDF, jpg o PNG. Agregar
> dos botones en el diálogo: "Subir" y "Cancelar". Al presionar "Subir" debe mostrarse
> un icono de congrats y se debe cambiar el estado a "pendiente_verificacion_comprobante".
> Mostrarle al usuario una pantalla acorde explicándole que el proceso de verificación
> es manual y que tomará como mucho 24hs. Desde el panel de control, el admin debe
> visualizar en grande y visible con alta prioridad que se ha cargado un nuevo
> comprobante y al acceder, mostrar un botón de confirmar y otro de rechazar. El botón
> de confirmar pasa el pago a "confirmado" y el pedido a "pendiente_preparacion". En
> caso de rechazar, el estado del pago pasa a "rechazado" y el del pedido "cancelado".
> 3) NO se puede reenviar. 4) Una vez que el pedido pase al estado entregado, el
> comprobante puede borrarse del pedido; solo en ese pedido queda el historial del
> medio de pago: transferencia.

## Decisiones de producto

- **D1 (aprobada)** — Gate: no hay pago `transfer` sin comprobante. `PATCH
  /orders/{id}/paid` sobre pedido `transfer` sin comprobante → 409 `receipt_required`.
  Con comprobante, el marcar pagado manual equivale a confirmar el comprobante (mismo
  use case que el botón del panel).
- **D2 (aprobada)** — Canales: solo portal (cliente sube) y panel (admin valida). v1 sin
  WhatsApp.
- **D3 (aprobada)** — Un comprobante por pedido, irrevocable: no reenvío, no
  reemplazo, ni tras un rechazo (rechazo → pedido `cancelled`, terminal).
- **D4 (aprobada)** — Borrado solo con pedido `delivered`: se elimina el archivo del
  storage, se limpian los campos, queda entrada de auditoría en `payment_events` y el
  pedido conserva `payment_method=transfer` (historial del medio de pago).
- **D5 (Hermes, vetoable)** — "Pendiente verificación de comprobante" es un estado de
  **presentación derivado** (portal + panel), no un nuevo valor de `OrderStatus`: cero
  migración, cero cambios en la máquina O1, misma UX. Derivación: `payment_method
  = transfer ∧ comprobante cargado ∧ payment_status = pending ∧ pedido no terminal`.
- **D6 (Hermes, vetoable)** — El gate aplica a todo pedido `transfer` sin importar
  origen. Un pedido `transfer` creado desde el panel puede cargar comprobante desde el
  panel (el admin lo adjunta en nombre del cliente, p. ej. screenshot de WhatsApp). Sin
  columna `order_source` nueva.
- **D7 (Hermes, vetoable)** — Las 24 h son una promesa de servicio de la copy del
  cliente ("verificación manual, hasta 24 hs"), no un timeout automático. El
  vencimiento automático por comprobante ausente queda fuera de scope (el timeout
  24 h `new → cancelled` sigue en fase 2 de O1).
- **D8 (Hermes, vetoable)** — Formatos: PDF, JPEG y PNG verificados por **magic bytes**
  (no WebP). Tamaño ≤ 5 MB. Sin dimensión mínima (los screenshots bancarios varían).

## Contradicción de spec resuelta (security #16)

`security.md` #16: "v1 sin uploads de usuario, con la excepción del upload de imagen de
producto". Se resuelve como O4 la resolvió: la pieza en conflicto se difiere y la
excepción se hace explícita. Nueva excepción: **comprobante de transferencia** —
multipart del cliente del portal (solo sobre su pedido) y del admin, magic bytes,
≤ 5 MB, nombre de archivo por id del pedido, storage **fuera del webroot y sin mount
público** (a diferencia de P12, que monta `/media`), entrega únicamente por endpoint
autenticado (`GET /orders/{id}/receipt`, owner o admin). `security.md` y
`api_endpoints.md` se actualizan en el mismo PR.

## Estados (fuente de verdad)

- `PaymentStatus` (O2): **sin valores nuevos**. Confirmar = `pending → approved`;
  rechazar = `pending → rejected` (ambas transiciones ya existen en la máquina O2).
- `OrderStatus` (O1): **una extensión de máquina** — `new → cancelled` (sin efecto de
  stock: un pedido no confirmado no tuvo descuento). Cadena de confirmación:
  `new → confirmed → preparing` (el descuento de stock ocurre en confirmar, efecto O1)
  ejecutada como operación atómica de dominio; si el pedido ya está en `confirmed`
  (confirmación manual previa desde el panel), la cadena es solo `confirmed →
  preparing`. Rechazo desde `preparing` → `cancelled` (efecto O1: restauración de
  stock).
- Estado de presentación (D5): label "Pendiente verificación de comprobante" (portal) y
  badge (panel). Sin valor persistente.

## API (todos bajo `/api/v1/orders`, sesión cookie)

| Método | Ruta | Rol | Contrato |
|--------|------|-----|----------|
| POST | `/orders/{id}/receipt` | owner (portal) o admin | multipart campo `file` → 201 (detalle actualizado) · 404 (pedido ajeno o inexistente, anti-sondeo) · 409 `receipt_method_not_transfer` / `receipt_already_uploaded` (D3) / `receipt_payment_not_pending` / `receipt_order_terminal` · 422 `receipt_invalid_type` (magic bytes) / `receipt_too_large` (> 5 MB) |
| GET | `/orders/{id}/receipt` | owner o admin | 200 binario (`Content-Type` real, `Content-Disposition: inline`) · 404 `receipt_not_found` (pedido ajeno o sin comprobante) · el primer GET de admin setea `receipt_viewed_at` |
| DELETE | `/orders/{id}/receipt` | admin only | 204 · 404 `receipt_not_found` · 409 `receipt_not_deletable` (solo `delivered`, D4) |
| POST | `/orders/{id}/receipt/confirm` | admin only | 200 (detalle actualizado) · 404 `receipt_not_found` · 409 `receipt_payment_not_pending` / `receipt_order_not_receivable` |
| POST | `/orders/{id}/receipt/reject` | admin only | 200 (detalle actualizado) · 404 `receipt_not_found` · 409 `receipt_payment_not_pending` / `receipt_order_not_cancellable` |

Schemas: el detalle de pedido (portal y admin) y el listado de pedidos ganan
`receipt_uploaded: bool`, `receipt_content_type: str | null`, `receipt_uploaded_at:
str | null`, `receipt_viewed_at: str | null` (datos para la derivación D5; el binario
nunca viaja por JSON).

## Specs

- **S1 — Servicio de storage `receipt_service.py`** (junto a `image_service.py` de P12,
  mismo estilo): `validate_receipt(data) -> str` con magic bytes — PDF `%PDF-`
  (primeros 5 bytes), JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A` — → `receipt_invalid_type`;
  `len(data) > 5 MiB` → `receipt_too_large`; devuelve la extensión (`pdf`/`jpg`/`png`).
  Storage: `backend/data/receipts/<order_id>.<ext>` (directorio gitignored, fuera del
  webroot, **nunca** montado como estático); `write_receipt(order_id, data, ext)`
  (sobrescritura imposible por D3: el caller valida antes), `read_receipt(order_id,
  ext)`, `delete_receipt(order_id, ext)`. La extensión viene de la validación, jamás del
  `Content-Type` ni del nombre del cliente.
- **S2 — Migración `0021_orders_receipt.sql` + ORM + schemas.** Columnas nullable en
  `orders`: `receipt_file TEXT`, `receipt_content_type TEXT`, `receipt_size_bytes INT`,
  `receipt_uploaded_at TIMESTAMPTZ`, `receipt_viewed_at TIMESTAMPTZ`,
  `receipt_deleted_at TIMESTAMPTZ`. `OrderORM` + campos en `Order` portal
  (`domain/order.py`) con validación coherente (comprobante solo con
  `payment_method=transfer`); schemas Response de detalle y listado con los 4 campos
  D5. Sin lógica de negocio en la migración (columnas puras).
- **S3 — `UploadReceipt` + `DeleteReceipt` (use cases, dominio).** `UploadReceipt`:
  pedido propio (owner) o admin (D6) → `payment_method=transfer` → sin comprobante (D3)
  → `payment_status=pending` → pedido no terminal → `validate_receipt` → escribir
  archivo → persistir campos + auditoría en `payment_events` (upload). El repository
  solo persiste lo decidido (regla 2026-11-23). `DeleteReceipt`: admin → pedido
  `delivered` (D4) → borrar archivo, nullar `receipt_file`/`content_type`/
  `uploaded_at` (conservando `deleted_at` + `payment_events`), `payment_method` intacto.
  Errores de dominio → 409 con los códigos de la tabla.
- **S4 — Extensión de máquina O1 + `ConfirmReceipt` / `RejectReceipt`.**
  `domain/order_states.py` (rama de O1): agregar `new → cancelled` (sin efecto de
  stock); tests de matriz 6×6 → 7×... ampliados (transición válida nueva + resto
  invariable, mensaje exacto `"Transicion invalida: {current} -> {target}"`).
  `ConfirmReceipt`: comprobante presente → pago `pending → approved` (máquina O2) +
  `paid`/`paid_at` (monótono) + pedido `new → confirmed → preparing` (o `confirmed →
  preparing`) con efecto de stock en confirmar (use case O1) → auditoría.
  `RejectReceipt`: comprobante presente → pago `pending → rejected` + pedido
  `new|confirmed|preparing → cancelled` (efecto O1 de restauración de stock cuando
  aplica) → auditoría. Estados de pedido terminales o `pending_delivery` → error de
  dominio (409 de la tabla).
- **S5 — Gate de marcar pagado (modificación de contrato O4).**
  `mark_manual_payment` (O4): para `TRANSFER` sin comprobante → `ReceiptRequiredError`
  → 409 `receipt_required` (D1); con comprobante → delega a `ConfirmReceipt` (idéntico
  al botón del panel). `CASH` y `MERCADOPAGO` inalterados (O4). El contrato de O4
  "el admin lo marca pagado al recibir la transferencia" queda **reemplazado** por
  "el pago se confirma vía comprobante".
- **S6 — Portal: congrats + diálogo + pantalla de espera + mis pedidos.**
  `CheckoutSuccess` (`StepReview.tsx`): si `payment_method=transfer`, card de warning
  (Chakra `Alert` tone warning) con el copy literal "Para confirmar su pedido, por
  favor suba el comprobante de la transferencia." + botón grande "Subir comprobante" →
  `AlertDialog` con zona drag & drop + input de archivo (acepta `.pdf`/`.jpg`/
  `.jpeg`/`.png`, validación client-side de extensión) + botones "Subir" y
  "Cancelar" (envío multipart vía `apiFetch`, que ya soporta FormData). Tras 201: icono
  de congrats + estado derivado pendiente_verificacion_comprobante (label "Comprobante
  en verificación") + pantalla de espera: "La verificación es manual y toma hasta 24
  horas." (D7). `MyOrdersPage`: pedido `transfer` sin comprobante → misma card + botón
  (entry point persistente); con comprobante → indicador "Comprobante en verificación"
  (sin botón de subida, D3). Pedido de otro método: cero cambios.
- **S7 — Panel admin: prioridad alta + validar + borrar.** `OrdersPage`: badge de alta
  prioridad en pedidos `transfer` con comprobante pendiente: acento fuerte + "Comprobante
  nuevo" mientras `receipt_viewed_at` sea null (se marca al abrir el comprobante), luego
  "Comprobante pendiente" (ámbar). `OrderDetailPage`: banner prominente "Comprobante de
  transferencia cargado" + preview (imagen inline vía `GET` autenticado; PDF con enlace
  de apertura en nueva pestaña) + botón "Confirmar comprobante" (verde) y "Rechazar
  comprobante" (rojo, `AlertDialog` de irreversibilidad: rechazo → pedido cancelado).
  Con pedido `delivered` + comprobante: botón fantasma "Borrar comprobante"
  (`AlertDialog`: se pierde el archivo, el historial del medio de pago queda en el
  pedido). El botón "Marcar pagado" de O4 para `transfer` se oculta cuando hay
  comprobante pendiente (los botones del comprobante son el flujo) y queda deshabilitado
  con tooltip cuando no hay comprobante (D1). Tokens derivados usados en el diseño de
  pantallas (board O5) a registrar en `theme.ts` y DESIGN.md: `warning.subtle` #fdf1e7,
  `warning.border` #ecd0b0, `red.subtle` #fdf1f1, `red.border` #eec6c6; botón "Confirmar
  comprobante" = fill teal (estado positivo, "verde" de S7). Regla de color del panel
  (aprobada 24/11): badges de estado/pago neutros (muted); warning sólido solo para
  "Comprobante nuevo" y warning suave para "Comprobante pendiente" — lo fuerte de la
  paleta solo donde hay que actuar.
- **S8 — Tests.** Unitarios: `receipt_service` (magic bytes positivos/negativos,
  content-type falsificado, 5 MiB límite, extensiones); dominio (matriz de máquina
  extendida, `ConfirmReceipt` desde `new` y desde `confirmed`, `RejectReceipt` desde
  `new`/`confirmed`/`preparing`, monotonía de `paid`, gate D1/D6, irreversibilidad D3,
  borrado D4); integración API: cada código de la tabla de endpoints (404 ajeno, 409
  por estado, 422 por tipo/tamaño, 200 binario con `Content-Type` correcto, DELETE solo
  `delivered`, `receipt_viewed_at` seteado por admin y no por owner). E2E: casos R1–R15
  de abajo. Gate frontend: vitest para la derivación D5, el diálogo y los badges.
- **S9 — Docs.** `security.md` #16: excepción de comprobante (como la de P12);
  `api_endpoints.md`: los 5 endpoints + esquema; `master_plan.md`: nota del flujo
  `transfer` (comprobante como gate de pago); `p06_orders.md`: referencia a este ODD en
  lugar de "efectivo en entrega" genérico para `transfer`.

## Tasks

| ID | Specs | Ruta | Definition of Done | Estado | Commit |
|----|-------|------|--------------------|--------|--------|
| T1 | S1 | inline | `receipt_service.py` + tests unitarios RED→GREEN: 3 magic bytes correctos, falsificaciones rechazadas, límite 5 MiB, write/read/delete contra tmp. | pending | — |
| T2 | S2 | inline | Migración 0021 idempotente + `OrderORM` + dominio + schemas; tests de integración: campos persisten, response detail/list incluyen los 4 campos, pedido sin comprobante devuelve `receipt_uploaded=false`. | pending | — |
| T3 | S4 | inline | Extensión `new → cancelled` de la máquina (matriz ampliada, mensaje exacto) + `ConfirmReceipt`/`RejectReceipt` + tests unitarios RED→GREEN (cadenas desde `new` y `confirmed`, rechazos desde 3 estados, monotonía de `paid`, audit). | pending | — |
| T4 | S3, S4, S5 | inline | Endpoints (5) + gate de marcar pagado + tests de integración RED→GREEN contra la tabla completa de contratos (todos los códigos, owner vs admin, anti-sondeo 404, binario stream). | pending | — |
| T5 | S6 | inline | Portal: `CheckoutSuccess` (card warning + botón + diálogo + pantalla de espera) + `MyOrdersPage` (entry point + indicador); vitest RED→GREEN de la derivación D5 y del envío multipart. | pending | — |
| T6 | S7 | inline | Panel: badges (`OrdersPage`), banner + preview + Confirmar/Rechazar/Borrar (`OrderDetailPage`), ocultación del botón de O4; vitest RED→GREEN de badges y botones por estado. | pending | — |
| T7 | S8 | inline | Suite e2e R1–R15 contra uvicorn + Postgres reales (mock MP); todo verde, base throwaway eliminada. | pending | — |
| T8 | S5 | delegado (verifier) | Verificador independiente contra S1–S7 + baseline de suites (pagos O4, backend completa, gate frontend, e2e) antes de reportar. | pending | — |
| T9 | S9 | inline | `security.md`/`api_endpoints.md`/`master_plan.md`/`p06_orders.md` actualizados; ruff/mypy limpios en archivos tocados; cero comentarios nuevos. | pending | — |

## Casos de prueba (autoritativos, e2e)

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| R1 | Cliente crea pedido transfer | `POST /orders/` (transfer) | 200; `payment_status=pending`, `receipt_uploaded=false` |
| R2 | Pedido transfer sin comprobante | Cliente `POST /orders/{id}/receipt` (JPEG válido, 1 MB) | 201; comprobante persistido, `uploaded_at` set, pago sigue `pending` |
| R3 | Pedido con comprobante | Cliente `POST` de nuevo (cualquier archivo) | 409 `receipt_already_uploaded` (D3) |
| R4 | Pedido cash | Cliente `POST /orders/{id}/receipt` | 409 `receipt_method_not_transfer` |
| R5 | GIF con `Content-Type: image/jpeg` | Cliente `POST` receipt | 422 `receipt_invalid_type` (magic bytes) |
| R6 | Archivo de 6 MB | Cliente `POST` receipt | 422 `receipt_too_large` |
| R7 | Pedido de otro cliente | Cliente `POST` / `GET` receipt | 404 |
| R8 | Pedido transfer `new` con comprobante | Admin `POST /orders/{id}/receipt/confirm` | 200; pago `approved`, `paid=true`, `paid_at` set; pedido `preparing`; stock descontado una sola vez |
| R9 | Pedido transfer `new` con comprobante | Admin `POST /orders/{id}/receipt/reject` | 200; pago `rejected`; pedido `cancelled` |
| R10 | Pedido con comprobante, ya `cancelled` | Admin `POST` confirm | 409 `receipt_order_not_receivable` |
| R11 | Pedido transfer sin comprobante | Admin `PATCH /orders/{id}/paid` | 409 `receipt_required` (D1) |
| R12 | Pedido `delivered` con comprobante | Admin `DELETE /orders/{id}/receipt` | 204; archivo borrado del disco, campos null, `deleted_at` set, `payment_method=transfer` intacto, entrada en `payment_events` |
| R13 | Pedido `preparing` con comprobante | Admin `DELETE /orders/{id}/receipt` | 409 `receipt_not_deletable` (D4) |
| R14 | Pedido sin comprobante | Admin `GET /orders/{id}/receipt` | 404 `receipt_not_found` |
| R15 | Pedido con comprobante | Cliente `GET /orders/{id}/receipt` | 200 binario íntegro, `Content-Type` real; `receipt_viewed_at` **no** cambia (solo admin lo setea) |

## Reglas

- Cero lógica de negocio en consultas a Postgres ni transacciones: la decisión de
  transición, el gate y los efectos viven en dominio; el repository solo persiste lo
  decidido (regla 2026-11-23).
- Cero comentarios en código nuevo; la spec es el contrato.
- Un archivo se toca una sola vez por entrega; commit por tarea; ruff/mypy limpios en
  archivos tocados.
- Baselines antes de reportar: suite de pagos (contrato O4), suite backend completa,
  gate frontend, e2e.
- El binario nunca viaja por JSON; nunca se expone nombre de archivo del cliente; nunca
  mount público de `backend/data/receipts`.

## Log

- **L1 — 2026-11-24 (pedido verbatim):** ver sección "Pedido del usuario" arriba.
- **L2 — 2026-11-24:** Decisiones D1–D4 aprobadas por el usuario (gate estricto,
  canales portal+panel, sin reenvío, borrado solo en `delivered` con historial de medio
  de pago). D5–D8 propuestas por Hermes y vetoables: estado derivado sin nueva máquina,
  gate sin discriminar origen (el panel carga por el cliente), 24 h como copy sin
  timeout automático, formatos PDF/JPEG/PNG por magic bytes.
- **L3 — 2026-11-24:** Hallazgos del mapeo: (1) pantalla de congrats = `CheckoutSuccess`
  exportado desde `StepReview.tsx` (estado `placed` en `CheckoutFlow`); (2) patrón P12
  como molde (`image_service.py`: magic bytes, 5 MiB, error codes) — diferencia
  deliberada: el comprobante es privado, sin mount `/media`; (3) `PaymentMethod.TRANSFER`
  ya existe en `domain/order.py` (main); (4) la migración 0020 vive en la pila de O1 →
  este ODD usa 0021; (5) la máquina O1 no permite `new → cancelled` → extensión
  obligatoria (S4) para el rechazo sin confirmación previa, sin efecto de stock; (6) la
  máquina O2 ya permite `pending → approved` y `pending → rejected` → cero cambios de
  valores; (7) el botón "Marcar pagado" de O4 ya existe en el panel (verificado en O4
  T6) → S5 reemplaza su contrato para `transfer`; (8) `apiFetch` ya soporta FormData sin
  `Content-Type` explícito (precedente P12) → el diálogo reutiliza el mismo camino.
- **L4 — 2026-11-24:** Riesgos: (1) el gate D1 toca el contrato de O4 (PR #88, abierto)
  — el stack debe mergear O4 antes que este ODD o el e2e R11 no tiene base; (2)
  `receipt_viewed_at` como señal de "nuevo" para la prioridad alta del panel: si el
  admin abre el listado pero no el comprobante, el badge de acento fuerte persiste (es
  el comportamiento querido: alta prioridad hasta que se mira); (3) el diálogo de
  upload en móvil (drag & drop no existe) → el input de archivo es el camino primario
  táctil; verificar en T5.

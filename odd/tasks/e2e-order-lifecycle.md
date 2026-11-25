# E2E: ciclo de vida de pedido + maquina de estados de pago (GIVEN-WHEN-THEN)

## Objetivo

Suite e2e de nivel API (servidor vivo + Postgres real) que cubre el ciclo de vida
completo del pedido —cliente crea, admin transiciona, se entrega— y la maquina de
estados de pago de `payment-states` (webhook Mercado Pago + pago manual), con casos
en formato **GIVEN-WHEN-THEN**. Cada caso debe pasar. Si un caso falla: fix en esta
rama (stacked sobre `feat/payment-states`, PR apilado sobre #86), commit por fix y
re-ejecucion completa hasta todo verde.

## Fuente de verdad

- Maquina de pedido: `backend/src/domain/order_states.py` (O1, PR #85).
- Maquina de pago: `backend/src/domain/payment_states.py` (O2, PR #86).
- Contrato de error de transicion invalida: `400 {"detail": "Transicion invalida: {current} -> {target}"}`.
- Webhook MP: `backend/src/api/v1/webhooks/router.py` + firma `verify_mp_signature`.
- Pago manual: `PATCH /api/v1/orders/{id}/paid` (`mark_order_paid`).

## Specs

- **S1 — Alcance**: creacion de pedido (cliente), maquina de estados del pedido
  (admin), maquina de estados de pago (webhook MP + marcado manual), RBAC y
  anti-sondeo.
- **S2 — Nivel**: e2e HTTP real contra `uvicorn` (proceso separado, no ASGI
  in-process, sin DI override). Unica frontera mockeada: la API de Mercado Pago
  (mock HTTP local en el boundary de red, apuntado via env `MP_API_URL`).
- **S3 — Base de datos**: `toscana_e2e_db` throwaway, drop+create por corrida
  (salvo fallo: se conserva para inspeccionar). Seed idempotente: usuarios
  (1 admin, 2 clientes), 1 ingrediente, 1 producto con receta; precios derivados.
- **S4 — Estructura del caso**: `GIVEN` (precondicion sembrada) / `WHEN` (accion
  HTTP) / `THEN` (asercion de estado + contrato de error exacto). El harness solo
  hace HTTP y asiertea; cero logica de negocio en el harness.
- **S5 — Aislamiento**: cada caso crea su pedido propio (Idempotency-Key propia);
  un caso no depende del estado residual de otro. Casos que cierran el order
  window lo re-abren al terminar.
- **S6 — Auditoria de eventos**: la asercion de "evento auditado" lee la tabla
  `payment_events` (efecto colateral de persistencia; el harness lo verifica, no
  lo decide).
- **S7 — Ejecucion**: `python backend/e2e/run.py` levanta mock MP + DB e2e +
  uvicorn, corre todos los casos y hace teardown (server, mock; DB drop solo si
  todo verde). Exit code 0 = todo verde.
- **S8 — Alcance MP de la maquina de pago (contrato preexistente, documentado)**:
  la maquina de pago se aplica solo a pedidos `mercadopago` (guard de
  `apply_payment_event` del repo, previo a O2). Cash usa el flag `paid`
  (`mark_cash_payment`) y su `payment_status` permanece `null`. Un webhook MP
  valido que referencia un pedido cash se audita en `payment_events` sin cambio
  de estado ni `paid` (proteccion: un evento de provider no puede marcar pagado
  un pedido que nunca entro al checkout). Los casos C1–C5 y C7 usan pedidos MP,
  que es el unico flujo real de webhook.

## Casos de prueba (autoritativos)

### A — Creacion de pedido (cliente)

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| A1 | Cliente autenticado; producto con precio derivado; order window abierto | POST `/orders/` (cash, delivery, 2 uds, `Idempotency-Key`) | 200; `status=new`, `payment_status=null`, `paid=false`, `total = 2 × precio derivado` |
| A2 | Order window cerrado | POST `/orders/` valido | 409 `order_window_closed` (header `Retry-After` si `reopens_at` set) |
| A3 | Pedido ya creado con key K y body B | POST `/orders/` con key K + body B + mismo usuario | Mismo pedido (id igual), sin duplicado |
| A4 | Pedido ya creado con key K y body B | POST `/orders/` con key K + body distinto + mismo usuario | 422 `idempotency_key_mismatch` |
| A5 | Cliente es dueño de un pedido | El cliente hace PATCH `/orders/{id}/status` | 403 |
| A6 | Cliente B tiene un pedido ajenos | Cliente A hace GET `/orders/mine/{code_b}` | 404 (anti-sondeo) |

### B — Maquina de estados del pedido (admin)

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| B1 | Pedido `new` | Admin: `new→confirmed→preparing→pending_delivery→delivered` | 200 en cada paso; estado final `delivered` |
| B2 | Pedido `new` | Admin intenta `new→delivered` | 400 `Transicion invalida: new -> delivered`; estado sigue `new` |
| B3 | Pedido `confirmed` | Admin → `cancelled` | 200; estado `cancelled` |
| B4 | Pedido `preparing` | Admin → `cancelled` | 200; estado `cancelled` |
| B5 | Pedido `new` | Admin → `cancelled` | 200; estado `cancelled` (habilitado en T3/O5: rechazo de comprobante y cancelación temprana, sin efecto de stock) |
| B6 | Pedido `delivered` | Admin → cualquier estado | 400 (terminal); estado sigue `delivered` |
| B7 | Pedido `cancelled` | Admin → cualquier estado | 400 (terminal); estado sigue `cancelled` |

### C — Maquina de estados de pago

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| C1 | Pedido MP sin `payment_status`; webhook MP aprobado (firma valida, monto y ARS correctos) | POST `/webhooks/mercadopago` (status `approved`) | `payment_status=approved`, `paid=true`, `paid_at` set |
| C2 | Pedido MP sin `payment_status` | Webhook `pending` y luego webhook `approved` (2 eventos) | Final `approved` (None→pending→approved) |
| C3 | Pedido con `payment_status=rejected` (webhook `rejected` previo) | Webhook `approved` | `approved` (desbloqueo; pago tardio) |
| C4 | Pedido MP `approved` (webhook previo) | Webhook `rejected` tardio con `event_id` nuevo | 200; estado sigue `approved`; evento persistido en `payment_events` (auditoria, S6) |
| C5 | Webhook `approved` con `event_id E` ya procesado | Replay del mismo webhook (misma firma, mismo `data.id`) | 200; sin cambio de estado; sin fila duplicada en `payment_events` |
| C6 | Webhook con firma invalida | POST `/webhooks/mercadopago` con `x-signature` corrupta | 401 `Invalid signature` |
| C7 | Pedido MP sin pago; webhook `approved` con monto incorrecto | POST `/webhooks/mercadopago` (amount ≠ total) | 200; estado sin cambio, `paid=false` (discrepancia logueada, no pagado) |
| C8 | Webhook cuyo `data.id` apunta a un pedido inexistente | POST `/webhooks/mercadopago` | 200 (no 500); sin estado que cambiar |
|| C9 | Pedido cash sin pago | Admin PATCH `/orders/{id}/paid` | 200; `paid=true`, `paid_at` set, `payment_status=null` (S8) |
| C10 | Pedido ya `paid` | Admin PATCH `/orders/{id}/paid` otra vez | 409 `order_already_paid` |
| C11 | Pedido MP con `payment_status=pending` (webhook previo) | Admin PATCH `/orders/{id}/paid` | 200; `paid=true`, `payment_status=approved` (confirmacion manual) |
|| C12 | Pedido MP con `payment_status=rejected` (webhook previo) | Admin PATCH `/orders/{id}/paid` | 409 `payment_in_progress` |
| C13 | Pedido CASH; webhook MP valido que lo referencia (anomalia de datos, S8) | POST `/webhooks/mercadopago` (status `approved`, firma valida) | 200; estado y `paid` sin cambio; evento auditado en `payment_events` (S6) |

## Tasks

- **T1** — ODD (este archivo) — `done`
- **T2** — Harness e2e: `backend/e2e/` con `mp_mock.py` (mock MP en el boundary de red), `seed.py` (DB throwaway + seed idempotente), `run.py` (orquestacion: mock + DB + uvicorn + casos + teardown). Aceptacion: `run.py` levanta todo, corre un caso de humo (login admin + cliente) y baja todo; exit 0. — `done`
- **T3** — Casos A + B en `backend/e2e/cases.py`. Aceptacion: A1–A6 y B1–B7 ejecutados contra el server vivo con aserciones exactas. — `done`
- **T4** — Casos C (C1–C13, ver L3) + cambio de testabilidad `MP_API_URL` via env en `backend/src/data/payments/mercadopago.py` (default unchanged). Aceptacion: C1–C13 ejecutados; el mock MP es la unica frontera externa. — `done`
- **T5** — Ejecucion completa (`python backend/e2e/run.py`). Aceptacion: 20/20 verde → cerrar; si hay fallo → fix separado por causa + re-ejecucion completa + log L* con el bug y el fix. — `done` (26/26, L2–L4)

## Reglas

- Fix en esta rama SOLO para bugs que un caso descubra (o el cambio de testabilidad
  de T4); sin refactor ajeno.
- Commit por tarea y commit por fix; ruff/mypy limpios en archivos nuevos.
- La suite no entra a CI (requiere Postgres local + puerto libre); se documenta en
  `backend/e2e/README.md`.

## Log

- **L1** (T1): 20 casos; 6 de creacion/RBAC, 7 de maquina de pedido, 12 de pagos
  (4 happy-path de maquina, 3 bordes de webhook, 4 de pago manual). Hallazgo de
  scope: `get_payment` del provider usa `MP_API_URL` hardcodeado — sin env no es
  posible apuntarlo al mock; se levanta como tarea T4 (cambio de testabilidad).
- **L2** (T5, primera ejecucion real): 15/25 verde; los 10 fallos fueron del
  harness, no del producto. Causas: (1) el detalle admin `GET /orders/{id}` no
  expone campos de pago → viven en `GET /orders/{id}/payment`; (2) la API expone
  `total` en centavos (Money) y el webhook valida en pesos → conversion en el
  harness; (3) order window = `PATCH /api/v1/tenant/order-window`. Bug de
  harness critico: `DATABASE_URL` se seteaba DESPUES de importar `e2e.seed`, que
  congela el engine de `data.db` → la primera corrida corrio contra la DB de
  desarrollo; se mueve el env antes de los imports + assert.
- **L3** (T5, hallazgo de contrato): los casos C1–C5 asumian que la maquina de
  pago se aplica a cualquier pedido; el guard de `apply_payment_event` (previo a
  O2, conservado por L2/L4 del ODD payment-states) restringe el UPDATE a
  `payment_method = mercadopago`. Cash: `paid` + `paid_at` via `mark_cash_payment`,
  `payment_status` permanece `null`; un webhook MP sobre pedido cash se audita sin
  cambio de estado (contrato conservador correcto — un evento de provider no
  marca pagado un pedido que no entro al checkout). **Cero cambio de producto**:
  se corrigen los casos (C1–C7 a pedidos MP, C9 al contrato cash real) y se
  documenta como S8 + caso C13 (borde no contemplado: webhook MP sobre cash).
- **L4** (T5, cierre): re-ejecucion completa → **26/26 verde** (25 + C13),
  exit 0, `toscana_e2e_db` dropada por teardown (regla: drop solo si todo verde).
  Cero cambios de producto en la rama: los fixes fueron del harness (contrato de
  endpoints, unidades de monto, ruta order-window, bug de orden de imports) y de
  spec (S8 + C13).
- **L5** (T7 O5, 2026-11-25): B5 actualizado — T3/O5 habilitó `new → cancelled`
  (flujo de rechazo de comprobante y cancelación temprana, sin efecto de stock);
  el caso e2e aserta 200 + `cancelled`. Suite e2e ahora 45 casos (secciones A/B/C/D
  + R del ODD de transfer receipt verification).

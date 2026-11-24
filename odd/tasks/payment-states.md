# O2 — Pago: máquina de estados GoF para PaymentStatus (mismo patrón que O1)

Objetivo: aplicar al estado de pago el mismo patrón establecido en O1 (order-prep-states): una máquina de estados GoF como única fuente de transiciones, centralizada en una nueva unidad de dominio, con cero lógica de negocio en SQL, TDD por tarea. **Sin migración de datos** (los valores ya están en inglés snake_case), **sin corte duro** (valores persistentes sin cambios) y **cero cambios de frontend** (el portal ya keyea los valores en inglés con labels propios).

Branch: `feat/payment-states` (worktree `.worktrees/paymentstates`), apilada sobre `feat/order-prep-states` (fase 2 de ese ODD, L5). Delivery: `ask-on-risk`.

## Máquina de estados (fuente de verdad)

Los valores de `PaymentStatus` ya persisten en inglés (`pending`, `approved`, `rejected`, `failed`) — sin migración. Hoy la "matriz" es implícita: `_PAYMENT_STATUS_RANK` + `overridable_payment_statuses()`, y **la decisión de transición vive en la WHERE clause SQL** de `apply_payment_event` (repository) — el anti-patrón que la regla del 2026-11-23 (cero lógica de negocio en SQL/transacciones) prohíbe. Este ODD la explicita **sin cambio de comportamiento observable**:

| Estado | Salidas |
|--------|---------|
| `None` (sin evento de provider) | `pending` · `approved` · `rejected` · `failed` |
| `pending` | `approved` · `rejected` · `failed` |
| `rejected` | `approved` |
| `failed` | `approved` |
| `approved` | — (terminal; paid es monotónico) |

Semántica preservada (de los ranks actuales):
- Un intento rechazado/fallido solo lo desbloquea un `approved` (el cliente reintenta y aprueba). Un evento `pending` de un intento nuevo NO resetea `rejected`/`failed` (el pedido mantiene el peor estado hasta que apruebe) — igual que hoy por el guard SQL.
- `approved` es terminal: paid/paid_at son monotónicos.
- Los eventos de pago (incluidos los que no cambian el estado) se registran en `payment_events` como audit; el dedup es por `event_id = {provider_payment_id}:{status}`.

## Specs

- **S1 — Máquina de estados `PaymentStatus` (patrón State, GoF).** Nueva unidad `domain/payment_states.py`: `PaymentStatus` (StrEnum, 4 miembros, **movido** de `domain/order.py`, valores sin cambio) + un estado concreto por valor con transiciones declarativas; `transition(current: PaymentStatus | None, target) -> PaymentStatus` levanta `InvalidPaymentTransitionError` con el mismo contrato de O1 (`"Transicion invalida: {current} -> {target}"`, atributos `.current`/`.target`); `state_for`/`is_known_payment_status`; `PAYMENT_STATUS_LABELS` en español derivado de los estados. `None` es estado de origen válido (sin evento aún) hacia cualquier valor.
- **S2 — Consumers.** `domain/order.py` deja de definir el enum, el rank y `overridable_payment_statuses` (importa la máquina); `__post_init__` valida `payment_status` contra la máquina (membership); `confirm_payment`/`register_payment_event` deciden vía la máquina (el guard de `paid`/cash se mantiene; `register_payment_event` queda tan restrictiva como el guard SQL que hoy aplica en el único flujo real — webhook — y no tiene callers en prod, solo tests). Webhook: nuevo use case `ApplyPaymentEvent` decide con la máquina (transición inválida → evento registrado para audit, sin cambio de estado); el repository **solo persiste lo decidido** (UPDATE con guard optimista de estado esperado, dedup por `event_id`). Schemas: `payment_status` de las respuestas → Literal de los 4 valores | None (hardening; valores sin cambio).
- **S3 — Sin regresiones.** Suite backend completa verde + gate frontend verde + verificador independiente contra S1–S2. Los tests existentes de pagos (webhook MP, expiry, transfer, attempt cycle, repository) deben pasar; solo se amplían/ajustan los unit de `register_payment_event` que codificaban la matriz ahora explícita.

## Tasks

| ID | Specs | DoD | Estado | Commit |
|----|-------|-----|--------|--------|
| T1 | S1 | `domain/payment_states.py` + `tests/unit/domain/test_payment_states.py` RED→GREEN: matriz 5 orígenes × 4 destinos (9 válidas / 11 inválidas con mensaje exacto y `.current`/`.target`), `None` hacia todo, `approved` terminal sin salidas, labels derivados, origen/destino desconocido levanta. | done | 0ea2b45 |
| T2 | S2 | `domain/order.py` sin enum/rank (importa la máquina); `__post_init__` valida membership; `confirm_payment`/`register_payment_event` vía máquina; use case `ApplyPaymentEvent` + `PaymentEventStore`; webhook vía use case; repository sin `overridable_payment_statuses` (guard de estado esperado); Literal en schemas; tests de pago verdes. | done | 1907503 |
| T3 | S3 | Suite completa backend + gate frontend + verificador independiente contra S1–S2; tabla actualizada. | done | — |

## Log

- **L1 — 2026-11-24 (pedido verbatim):** "excelente,ahora que ya tienes en tu conocimiento el workaround y la estructura de la máquina de estados,quiero que implementes el mismo patrón para el estado de los pagos" — mismo patrón que O1: máquina GoF + centralización + cero lógica de negocio en SQL + TDD.
- **L3 — 2026-11-24 (T1 done, 0ea2b45):** máquina GoF implementada con el mismo patrón que O1 (`order_states.py`): 4 estados concretos, `transition()` con contrato de error idéntico (mensaje + `.current`/`.target`), `None` como origen válido hacia cualquier valor, `PAYMENT_STATUS_LABELS` derivados. 21/21 tests. mypy clean en archivos nuevos; ruff clean (la deuda de los archivos tocados es preexistente: I001/FURB157/B008 presentes en HEAD).
- **L4 — 2026-11-24 (T2 done, 1907503):** consumers migrados sin cambio de comportamiento observable. (1) `domain/order.py` sin enum/rank/`overridable_payment_statuses` (0 referencias en src+tests); `__post_init__` valida membership de `payment_status`; `confirm_payment` (APPROVED-only + guard de máquina) y `register_payment_event` (no-APPROVED + guard de máquina) — los tests existentes (todos desde `None`) pasan sin tocar. (2) Webhook MP → use case `ApplyPaymentEvent` (dedup → máquina → persiste lo decidido; transición inválida → evento auditado sin cambio de estado). (3) `apply_payment_event` del repo: guard de estado esperado (`payment_status == current` o `IS NULL`) en lugar de `IN (replaceable)` — cero lógica de negocio en SQL. (4) Schemas: `Literal` de 4 valores en `PaymentStatusResponse.status` y `OrderResponse.payment_status`. (5) Suite de pagos: **131/131** (2 tests actualizados al nuevo contrato del repo: `test_orders_payment_expiry`, atomicidad del webhook). Bug cazado en el camino: `get_payment_event` retorna `bool` (no ORM) — el primer check de dedup del use case (`is not None`) siempre trueaba y tiraba todo a early-return; corregido a truthiness. Fuera de scope de este ODD (documentado): `claim/release_payment_pending` (ventana de intento, `None↔pending` no está en la matriz) y `expire_pending_payment` (fase 2 del ODD de pedidos: timeout 24 h).
- **L5 — 2026-11-24 (T3 done):** Suite completa backend: **2156 passed / 2 failed** — las 2 fallas son las preexistentes de `test_order_window_api.py` (TZ del host, documentadas en el ODD de pedidos L11; fallan igual en `origin/main`). Base anterior 2135 → +21 (tests de la máquina). Gate frontend: tsc 0 errores, vitest 587/587, `next build` exit 0 (solo el advisory de seguridad de Next.js en el primer intento, retry completa — pendencia separada conocida). Auditoría S1–S2: 0 refs de enum/rank/overridable en `domain/order.py`; 4 estados concretos; webhook vía use case; guard de estado esperado en repo; Literals en schemas; membership de `__post_init__` verificada en ambos sentidos (`weird` levanta, `pending` pasa). Cero cambios frontend (el portal ya keyea valores en inglés).
- **L2 — 2026-11-24 (hallazgo del mapeo):** (1) los valores ya están en inglés snake_case → **sin migración, sin corte duro, sin cambio de frontend** (el portal `MyOrdersPage` keyea `pending`/`rejected`/`failed` con labels propios — "valores son datos, label es presentación" ya cumplido); (2) la decisión de transición vive en la WHERE clause SQL de `apply_payment_event` (`IN (replaceable)` vía ranks) — viola la regla del 2026-11-23, este ODD la mueve a dominio; (3) `register_payment_event` no tiene callers en prod (solo tests) — el flujo real es webhook → `repo.apply_payment_event`; (4) `confirm_payment`/`mark_cash_payment` sí se usan en el router de orders (pago manual); (5) `payment_events` ya registra audit con dedup por `event_id`; (6) el mapa del provider MP normaliza a los 4 valores (`_STATUS_MAP`), origen desconocido → `pending`.

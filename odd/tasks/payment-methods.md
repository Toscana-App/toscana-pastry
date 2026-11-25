# Pagos por método: cash y transferencia en la maquina de estados

## Objetivo

Que los tres métodos de pago vivan en la misma maquina de estados de pago
(`payment-states`, PR #86) con un solo estado final compartido:

- **Cash**: el pedido nace "pendiente de pago"; cuando el admin cobra al
  retirar/entregar, pasa al estado final.
- **Transfer**: el pedido nace "pendiente de pago"; cuando el admin recibe la
  transferencia, marca el pago desde el panel y pasa al estado final.
- **Mercado Pago**: sin cambios (webhook-driven).

Estado final compartido = `approved` (el que ya usa el flujo MP). "Pendiente de
pago" = `pending` existente: no se agrega un quinto valor (un estado nuevo cuyo
único destino es `approved` no agrega información; la presentación por método
ya vive en los labels del frontend).

## Fuente de verdad

- Maquina de pago: `backend/src/domain/payment_states.py` (O2, PR #86) —
  `None|pending|rejected|failed → approved`; `approved` terminal.
- Orden dominio: `backend/src/domain/order.py` (`Order.place_portal`,
  `confirm_payment`, `register_payment_event`, `mark_cash_payment`).
- Pago manual: `PATCH /api/v1/orders/{id}/paid` (`mark_order_paid`).
- Webhook MP: `POST /api/v1/webhooks/mercadopago` → use case `ApplyPaymentEvent`
  → repo `apply_payment_event` (guard de `payment_method = mercadopago`,
  contrato S8 del ODD e2e-order-lifecycle).
- Frontend (sin cambios esperados): `MyOrdersPage.tsx` (`PaymentBadge` por
  método/estado), `StepPayment.tsx` (los 3 métodos ya ofrecidos),
  `OrderDetailPage.tsx` (botón "Marcar pagado").

## Specs

- **S1 — Estado inicial por método**: `place_portal` deja `payment_status =
  pending` para CASH y TRANSFER (pago pendiente de confirmación offline) y
  `None` para MERCADOPAGO (el pedido no inicia el flujo del provider hasta
  `POST /orders/{id}/payment`). La decisión vive en el dominio; el repo solo
  persiste.
- **S2 — Estado final único**: `approved` es "pagado" para los tres métodos
  (`paid_at` set, `paid=true`, monotónico). El pago manual de cash/transfer
  transiciona por la maquina (None/pending/rejected/failed → approved);
  `mark_cash_payment` se retira (su único caller de prod es el router).
- **S3 — Guard de provider**: solo MERCADOPAGO tiene eventos de provider.
  `register_payment_event` rechaza CASH y TRANSFER (hoy solo CASH); un webhook
  MP que referencia un pedido cash/transfer se audita en `payment_events` sin
  cambio de estado (S8 del ODD e2e, ahora para los dos métodos).
- **S4 — Pago manual por método** (`PATCH /orders/{id}/paid`):
  - CASH/TRANSFER: `None|pending → approved` (y `rejected|failed → approved`
    como re-confirmation, la maquina ya lo permite); `approved` ya pagado →
    409 `order_already_paid`.
  - MERCADOPAGO: sin cambios (None/pending → confirmed manual; rejected/failed
    → 409 `payment_in_progress` — el provider es la fuente de verdad).
- **S5 — Sin expiración offline**: `is_payment_expired` (24 h) sigue
  MP-only; cash/transfer no vencen (el pago se coordina con la entrega).
- **S6 — Compatibilidad sin migración**: pedidos legacy con
  `payment_status = null` siguen marcables (transición `None → approved`
  válida). No hay migración.
- **S7 — Frontend sin cambios**: los badges ya muestran "Pagar en efectivo en
  la entrega" / "Pagar por transferencia" (pending implícito por método) y
  "Pagado" cuando `paid`. El checkout ya ofrece los tres métodos. Si la
  verificación (T6) encuentra un gap, se corrige ahí.
- **S8 — Comprobante de transferencia (PENDIENTE, fuera de este PR)**: cliente
  adjunta imagen/PDF del comprobante bancario; el admin lo valida en el panel
  antes de marcar pagado. Requiere infraestructura de uploads (contradicción
  resuelta de la spec: security #16 "sin uploads" → se difiere la pieza en
  conflicto, no se elige uno de los dos). Va en un ODD/fase propia.
- **S9 — Fuera de scope**: regla "no entregar sin pago" (cruce maquina de
  pedido × pago). Si se quiere, ODD propio.

## Casos de prueba (autoritativos, e2e)

| ID | GIVEN | WHEN | THEN |
|----|-------|------|------|
| D1 | Cliente crea pedido cash | POST `/orders/` (cash) | 200; `payment_status=pending`, `paid=false` |
| D2 | Pedido cash `pending` | Admin PATCH `/orders/{id}/paid` | 200; `payment_status=approved`, `paid=true`, `paid_at` set |
| D3 | Cliente crea pedido transfer | POST `/orders/` (transfer) | 200; `payment_status=pending`, `paid=false` |
| D4 | Pedido transfer `pending` **con comprobante** | Admin PATCH `/orders/{id}/paid` | 200 (delega en `ConfirmReceipt`); `approved`, `paid=true`, `payment_reference=manual`. Sin comprobante: 409 `receipt_required` (gate O5/S5) |
| D5 | Pedido transfer; webhook MP valido que lo referencia | POST `/webhooks/mercadopago` (approved) | 200; estado sigue `pending`, `paid=false`; evento auditado (S3/S8) |
| D6 | Pedido cash `approved` (pagado) | Admin PATCH `/orders/{id}/paid` otra vez | 409 `order_already_paid` |

Cambios en casos existentes: A1 (`payment_status=null` → `pending`), C9 (cash
manual → `approved`, no `null`), C13 (webhook sobre cash: estado sigue
`pending`, no `None`).

## Tasks

- **T1** — ODD (este archivo) ✅
- **T2** — S1: `place_portal` con `payment_status=pending` para CASH/TRANSFER + tests de dominio ✅
- **T3** — S2+S3: `mark_manual_payment(reference)` (CASH/TRANSFER vía maquina) reemplaza `mark_cash_payment`; `register_payment_event` rechaza TRANSFER + tests de dominio ✅
- **T4** — S4: `mark_order_paid` — rama no-MP usa `mark_manual_payment` + tests de API (suite de pagos) ✅
- **T5** — e2e: D1–D6 + actualización de A1/C9/C13; ejecución completa verde ✅
- **T6** — Frontend: verificar S7 (badges/checkout/admin); solo si hay gap, fix + tests ✅ (audit previo: cero gaps, sin cambios)
- **T7** — (PENDIENTE) S8: comprobante de transferencia (uploads) — ODD/fase propia

## Reglas

- Cero lógica de negocio en SQL: la transición se decide en el dominio.
- Cero comentarios en código nuevo; la spec es el contrato.
- Un archivo se toca una sola vez por entrega; commit por tarea; ruff/mypy
  limpios en archivos tocados.
- Baselines antes de reportar: suite de pagos, suite backend completa,
  frontend (tsc/vitest/build) si T6 toca frontend.

## Log

- **L1** (T1): diseño — reuso de `pending` (no quinto valor); final único
  `approved`; guard de provider extendido a TRANSFER; comprobante documentado
  como T7 pendiente (contradicción de uploads); entrega sin pago fuera de
  scope (S9). Frontend auditado: cero cambios esperados (S7).
- **L2** (T2): S1 implementado en `place_portal` (offline → `pending`, MP →
  `None`); suite de dominio verde.
- **L3** (T3): `mark_manual_payment` (maquina, `reference`) reemplaza
  `mark_cash_payment`; `confirm_payment` MP-only; `register_payment_event`
  rechaza CASH+TRANSFER.
- **L4** (T4): `mark_order_paid` — cash y transfer pasan por
  `update_payment_status` (persiste status+reference+paid_at); la rama cash
  anterior solo seteaba `paid_at`.
- **L5** (T5): mapeo tabla de casos — D1/D2/D6 ya cubiertos por A1/C9/C10
  (actualizados al contrato nuevo); casos nuevos D3 (creación transfer), D4
  (pago manual transfer), D5 (webhook sobre transfer); D7 adicional (pago
  manual MP desde `None`, fuera de tabla) por la rama
  `confirm_payment` desde estado inicial.
- **L6** (T7 O5, 2026-11-25): D4 actualizado al gate O5/S5 — el pago manual de
  transfer delega en `ConfirmReceipt` y exige comprobante cargado (sin él, 409
  `receipt_required`); la referencia de pago queda `manual`.

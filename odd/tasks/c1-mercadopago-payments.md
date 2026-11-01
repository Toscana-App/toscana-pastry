# C1 — Pagos Mercado Pago + efectivo (backend)

**Tarea**: `c1-mercadopago-payments`
**Specs**: S3/S4 · `p06_orders.md` RF-P6-12/13/14 · `api_endpoints.md` §FASE 5 (pagos)
**Branch**: `feat/c1-mercadopago-payments` (base: `feat/portal-fase5`)
**Commit**: `feat(orders): pagos Mercado Pago (CheckoutProvider + mock) + webhook idempotente`

## Resumen

`order` gana `payment_method ∈ {mercadopago, cash}` (requerido desde portal; default `cash` en admin), `payment_reference?`, `paid_at?` (inmutables post-confirmación). Interfaz `CheckoutProvider` agnóstica + `MockCheckoutProvider` (IDs determinísticos, transiciones `pending → approved | rejected | failed`). Regla de `paid`: solo manual (dueña) o webhook, monótona `false → true`. API: `POST/GET /orders/{id}/payment` + `POST /webhooks/mercadopago` (firma + idempotencia + estados).

## Subtareas atómicas

### C1.0 — Merge P6 al stack

El módulo P6 de pedidos (dominio/API/data + tests) vive en `feat/phase6-backend` (→ phase7/8) y **NO está en `main` ni en `feat/portal-fase5`**; además `Order` no tiene aún `paid`/`payment_*` ni `PATCH /orders/{id}/paid`. C1 incluye C1.0 como primer subtask: merge de P6 al stack de Fase 5.

**Acción**: crear el módulo `order` (dominio, data, API) con los campos base de `Order` (`status`, `customer_id`, `date`, `items`, `paid`) y el endpoint `PATCH /orders/{id}/paid`.

**Precondición**: ninguna (es creación desde cero del módulo base).

**Definition of Done**:
- `domain/models.py` incluye `Order` con campos base (sin `payment_*` todavía).
- `data/models.py` incluye `OrderORM`.
- `data/repositories/sql_order_repository.py` con CRUD mínimo.
- `api/v1/orders/` router con `PATCH /orders/{id}/paid`.
- Tests: `test_order_domain.py` + `test_orders_paid_api.py`.
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.1 — Dominio: payment_method / payment_reference / paid_at

**Spec**: RF-P6-12.

**Acción**: agregar al dominio `Order`:
- `payment_method: PaymentMethod` (`mercadopago` | `cash`, default `cash`).
- `payment_reference: str | None` (id del pago del proveedor, server-managed).
- `paid_at: datetime | None` (timestamp server-managed).
- `payment_status: PaymentStatus | None` (`pending` | `approved` | `rejected` | `failed`, null en `cash`).

**Invariantes**:
- `payment_method` es inmutable tras la confirmación del pedido (`status != nuevo`).
- `paid` (bool derivado: `paid_at is not None`) es monótono `false → true`.
- En pedidos `cash`, `payment_status` es **siempre `None`**.

**Precondición**: C1.0 (módulo base con `Order`).

**Definition of Done**:
- `Order` domain dataclass con nuevos campos + validaciones.
- Tests unitarios: invariantes (payment_method inmutable post-confirmación, paid monótono, cash payment_status=null).
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.2 — Data: OrderORM + PaymentEventORM + repositorio

**Spec**: RF-P6-13 (webhook dedupe), RNF-P6-10 (dedupe persistente).

**Acción**:
- `OrderORM`: agregar columnas `payment_method`, `payment_reference`, `paid_at`, `payment_status`.
- `PaymentEventORM`: tabla para dedupe de webhook. Campos: `id` (id del pago del proveedor, único), `order_id`, `status`, `created_at`.
- `SQLOrderRepository`: métodos para actualizar `payment_*` y `paid_at`.

**Precondición**: C1.1.

**Definition of Done**:
- `data/models.py`: `OrderORM` actualizado + `PaymentEventORM`.
- `data/repositories/sql_order_repository.py`: métodos `update_payment_status`, `record_payment_event`, `get_payment_event`.
- Tests: `test_order_repository.py` (actualización de pago, dedupe de eventos).
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.3 — CheckoutProvider interface + MockCheckoutProvider

**Spec**: RF-P6-13 (contrato agnóstico, safe mode).

**Acción**:
- `domain/checkout_provider.py`: protocolo Python `CheckoutProvider` con:
  - `create_payment(order) → {reference, checkout_url}`
  - `get_payment(reference) → {status}`
  - `verify_webhook(payload) → payload verificado | None`
- `domain/mock_checkout_provider.py`: `MockCheckoutProvider`:
  - referencia determinística: `mock_<order_id>`
  - estado determinístico: último dígito de reference → `0` → `rejected`, `1` → `pending`, otro → `approved`
  - firma determinística: HMAC con constante de pruebas hardcodeada
  - cero I/O, sin red, sin aleatoriedad, sin reloj

**Precondición**: C1.1 (payment_method en Order).

**Definition of Done**:
- `domain/checkout_provider.py`: protocolo + tipos.
- `domain/mock_checkout_provider.py`: implementación mock.
- Tests unitarios: determinismo de estados, verificación de firma (válida/inválida), referencia determinística.
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.4 — POST /orders/{id}/payment

**Spec**: RF-P6-13 (endpoint, idempotencia, códigos de error).

**Acción**:
- `POST /orders/{id}/payment`:
  - Solo `status=nuevo` + `payment_method=mercadopago`
  - Header `Idempotency-Key` obligatorio
  - Misma key → misma respuesta guardada (200)
  - Otra key con `payment_status=pending` → 409 `payment_in_progress`
  - Estado terminal → 422 `payment_finalized`
  - `payment_method=cash` → 422 `payment_method_not_mercadopago`
  - `status ≠ nuevo` → 409 `order_not_payable`
  - Pedido de otro tenant → 404 anti-sondeo
  - Respuesta: `{reference, checkout_url}`

**Precondición**: C1.2 (OrderORM con payment_*), C1.3 (MockCheckoutProvider).

**Definition of Done**:
- `api/v1/orders/router.py`: endpoint `POST /orders/{id}/payment`.
- Tests: idempotencia, 409 payment_in_progress, 422 payment_finalized, 422 payment_method_not_mercadopago, 409 order_not_payable, 404 anti-sondeo.
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.5 — GET /orders/{id}/payment

**Spec**: RF-P6-13 (polling del portal).

**Acción**:
- `GET /orders/{id}/payment`:
  - Respuesta: `{status, paid, payment_reference?, updated_at?}`
  - `status` = `payment_status` (null si no se inició pago)
  - 404 anti-sondeo a pedidos ajenos

**Precondición**: C1.4.

**Definition of Done**:
- `api/v1/orders/router.py`: endpoint `GET /orders/{id}/payment`.
- Tests: response shape, null status, paid derivado, 404 anti-sondeo.
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.6 — POST /webhooks/mercadopago

**Spec**: RF-P6-13 (webhook, firma, dedupe, estados desordenados, transacción).

**Acción**:
- `POST /webhooks/mercadopago`:
  1. Validar firma vía `verify_webhook` → 401 si falla / 422 si payload inválido
  2. Dedupe por id de pago en `PaymentEvent` (único; replay → 200 sin efecto)
  3. Estados desordenados por prioridad: `approved > rejected = failed > pending`
     - `pending` nunca sobreescribe terminal
     - `approved` se aplica como máximo una vez (guard `WHERE paid=false`)
     - `rejected`/`failed` son intercambiables y **nunca revierten** `paid`
  4. `approved` → `paid=true` + `paid_at=now` + `payment_reference` + `payment_status=approved` en una transacción
  5. Con firma válida, siempre 200 `{"ok":true}`

**Precondición**: C1.5, C1.2 (PaymentEventORM).

**Definition of Done**:
- `api/v1/webhooks/router.py`: endpoint `POST /webhooks/mercadopago`.
- Tests: firma válida/inválida, dedupe/replay, estados desordenados, approved no revierte paid, cash permanece paid=false, transacción atómica.
- Suite: baseline + N tests nuevos, 0 regresiones.

### C1.7 — Tests de integración completos + gate

**Spec**: RNF-P6-08/09/10 (idempotencia, safe mode, concurrency).

**Acción**:
- `backend/tests/unit/domain/test_checkout_provider.py`: determinismo mock, contrato.
- `backend/tests/unit/domain/test_order_payment.py`: invariantes de pago.
- `backend/tests/integration/api/test_orders_payment_api.py`: todos los endpoints de pago.
- `backend/tests/integration/api/test_webhooks_mercadopago.py`: webhook completo.

**Precondición**: C1.6.

**Definition of Done**:
- Todos los tests pasan.
- `python -m pytest -q` verde (baseline + N nuevos, 0 regresiones).
- Safe mode verificable: no importa SDK de pagos, no lee env de credenciales, no llama API externa.

## Orden de ejecución

C1.0 → C1.1 → C1.2 → C1.3 → C1.4 → C1.5 → C1.6 → C1.7

## Gates

- Backend: `python -m pytest -q` verde (baseline + tests nuevos, 0 regresiones).
- Safe mode: `grep -r "mercadopago" backend/src/` solo aparece en `mock_checkout_provider.py` y `webhooks/router.py` (import del mock), NUNCA importa `mercadopago` como SDK.
- No env de credenciales: `grep -r "MP_" backend/src/` no encuentra nada.
- No llamadas externas: `grep -r "requests\|httpx\|aiohttp" backend/src/domain/` no encuentra nada.

## Log

L1 — 2026-10-26: C1 definido a partir de `p06_orders.md` RF-P6-12/13/14 + `api_endpoints.md` §FASE 5. Hallazgo: P6 orders no mergeado en el stack → C1.0 lo resuelve.

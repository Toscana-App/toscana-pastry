# P6 — Pedidos
Módulo: `web/modules/orders` · Rutas: `/pedidos`, `/pedidos/nuevo`, `/pedidos/{id}` · Fase: **2**

## Contexto
Gestión de pedidos de clientes. Screenshot verificado: "Pedido Sofía Molina" con ítems (torta 20 porciones, alfajores), desglose de insumos con costos, "Total gastos $31.500 · Trabajo $28.000 · Ganancia 35%: $20.825 · Precio final $80.325" y CTA **"Le paso $81.000"** (redondeo + envío por WhatsApp).

## User story
> Como **repostera**, quiero **registrar cada pedido con su costo real y enviarle el precio a la clienta por WhatsApp con un toque**, para **no perder pedidos ni calcular a mano**.

**Criterios de aceptación**
- [ ] Creo un pedido: cliente (nuevo o existente), productos con cantidad y ajuste de porciones.
- [ ] Veo el desglose completo: insumos unitarios, total de gastos, mano de obra, ganancia (con margen por pedido editable) y precio final redondeado.
- [ ] "Le paso $X" abre WhatsApp con el mensaje armado (ítems + total).
- [ ] Al confirmar el pedido, el stock se descuenta y queda registrado.
- [ ] Veo historial con estados (nuevo / confirmado / entregado) y busco por cliente.
- [ ] Marco un pedido como pagado sin tocar su estado de entrega; veo el contador de "sin pagar".
- [ ] Veo el resumen de la semana (pedidos, totales, pagado/pendiente) y exporto a CSV.
- [ ] Con los pedidos cerrados, veo el banner con el mensaje del negocio y no puedo crear.
- [ ] Un pedido puede pagarse con Mercado Pago (el pago se confirma solo, sin que yo lo marque) o en efectivo en la entrega (lo marco yo cuando cobra).

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver pedidos | Repostera | Lista con estado + búsqueda por cliente/fecha |
| UC-02 Crear pedido | Repostera | Cliente → ítems (productos + cantidad) → desglose en vivo → guardar |
| UC-03 Ajustar margen del pedido | Repostera | Cambia el % (override del default) → precio se recalcula |
| UC-04 Enviar precio por WhatsApp | Repostera | CTA "Le paso $X" → wa.me prellenado → marca enviado |
| UC-05 Confirmar pedido | Repostera | Estado → confirmado → stock descuenta (movimiento) |
| UC-06 Ver desglose | Repostera | Detalle: cada insumo, su cantidad y costo |
| UC-07 Marcar pago | Repostera | Toggle "Pagado" en el pedido (independiente de entrega) |
| UC-08 Resumen semanal | Repostera | Vista de la semana: pedidos, totales, pagado → export CSV |
| UC-09 Pedidos cerrados | Repostera | Banner del tenant visible; la creación queda bloqueada |
| UC-10 Pago Mercado Pago | Cliente/negocio (portal) | Crea el pedido → redirect a checkout del proveedor → webhook marca `paid` | 
| UC-11 Pago efectivo en la entrega | Cliente/negocio (portal) + Repostera | `paid=false` → la dueña lo marca al cobrar |

## Requerimientos funcionales
- **RF-P6-01**: CRUD de pedidos: `customer*`, `date`, `items[]` (producto, cantidad, nota de porción/tamaño), `status`. (UC-02)
- **RF-P6-02**: Desglose calculado por el motor: insumos (conversión según cantidad de porciones), total de gastos, mano de obra, margen % (default del tenant, **override visible por pedido**), ganancia, precio final, redondeo. (UC-02/03)
- **RF-P6-03**: Estados: `nuevo → confirmado → entregado` (+ `cancelado` desde confirmado, con re-pozo de stock). Transiciones validadas. (UC-05/06)
- **RF-P6-04**: Descuento de stock **atómico** al confirmar (transacción; si falta stock → error claro por insumo, sin confirmar). (UC-05)
- **RF-P6-05**: `stock_movement` por cada descuento (referencia al pedido). (UC-05)
- **RF-P6-06**: CTA WhatsApp: genera link `wa.me/?text=` con template (saludo, ítems con precios, total) y registra el evento. (UC-04)
- **RF-P6-07**: Búsqueda/filtro: por cliente, estado, rango de fechas. (UC-01)
- **RF-P6-08**: Reutilizar cliente: clientes se crean/reusan de una lista (sin duplicados exactos por nombre+teléfono). (UC-02)
- **RF-P6-09**: Corte de pedidos: si `order_window_open=false` (P5) → banner en lista y creación con `order_window_message`; `POST /orders` → 409 `{detail: order_window_closed, message}`. (UC-09)
- **RF-P6-10**: Estado de pago: `paid` (bool, server-managed, default false), **independiente** de la máquina de estados de entrega; `PATCH /orders/{id}/paid` (manual, por la dueña — caso efectivo); filtro `paid=false` ("Sin pagar") en la lista + contador en el header. El webhook de Mercado Pago (RF-P6-13) es la única otra vía de marcado. (UC-07/11)
- **RF-P6-12**: Método de pago: `payment_method ∈ {mercadopago, cash}` (requerido en creación desde el portal; default `cash` en creación desde el panel admin) + `payment_reference?` (id del pago del proveedor, server-managed) + `paid_at?` (timestamp server-managed). Inmutable tras la confirmación del pedido. (UC-10/11)
- **RF-P6-13**: Mercado Pago (contratos, safe mode de la skill `mercadopago-integration`): interfaz `CheckoutProvider` agnóstica de proveedor (`create_payment(order) → {reference, checkout_url}`, `get_payment(reference) → estado`, `verify_webhook(payload)`) con `MockCheckoutProvider` como implementación de referencia (IDs determinísticos, transiciones `pending → approved|rejected|failed`). Endpoints: `POST /orders/{id}/payment` (solo `status=nuevo` + `payment_method=mercadopago`; idempotente por `Idempotency-Key`) → `{reference, checkout_url}`; `GET /orders/{id}/payment` → `{status, paid, payment_reference?, updated_at?}` (polling del portal). Webhook `POST /webhooks/mercadopago`: verifica firma, dedupe por id de pago, estados desordenados tolerados (prevalece el final por prioridad `approved|rejected > pending`); `approved` → `paid=true` + `paid_at` + `payment_reference` en transacción. Antes de marcar `paid=true`, el backend consulta `get_payment(reference)` (no confía en el payload) y verifica que `external_reference` == id del pedido, `transaction_amount` == total del pedido post-cupón (sin tolerancia) y `currency_id` == moneda del tenant; si no coincide no marca `paid`, registra la discrepancia y responde 200 para evitar reintentos infinitos. El endpoint está deshabilitado (404/503) salvo que el provider activo sea live y tenga secreto configurado, o que el mock use un secreto HMAC propio de test; la verificación valida firma + `ts` (header `x-signature`) dentro de una tolerancia de timestamp anti-replay con `hmac.compare_digest`, y falla cerrado (401) ante secreto ausente. Los estados siguen la tabla de transiciones de pago (abajo). (UC-10)
- **RF-P6-14**: Efectivo en la entrega: `payment_method=cash` → el pedido permanece `paid=false` con badge "Cobrar en la entrega" (lista y detalle, texto no solo color); la dueña lo marca con el toggle de RF-P6-10. **Security Handoff** (requisito de la skill para el rollout live, fuera de esta specs): credenciales `MP_ACCESS_TOKEN`/`MP_WEBHOOK_SECRET` solo en env del backend; firma HMAC del webhook validada antes de cualquier efecto (requisitos mínimos de verificación en RF-P6-13); rate limit en el webhook; no se prescribe aquí SDK live ni creación de sesiones reales del proveedor.
- **RF-P6-11**: Resumen semanal: semana natural (Lun–Dom) con pedidos `confirmado`/`entregado` (cliente, ítems, total, pago), totales (`amount`, `paid`, `unpaid`) + export CSV `GET /orders/export` (y `GET /budgets/export` en F3). (UC-08)

**Transiciones de pago permitidas** (estado interno del polling `GET /orders/{id}/payment`):

| Desde | Hacia | Efecto |
|---|---|---|
| `pending` | `approved` \| `rejected` \| `failed` | `approved` → `paid=true` (previa validación de RF-P6-13) |
| `approved` | `refunded` | Alerta a la dueña; no revierte `paid` automáticamente |
| `approved` \| `rejected` \| `failed` | cualquier otro | No permitido: estados finales inmutables |

## Requerimientos no funcionales
- **RNF-P6-01**: Crear pedido con 10 ítems < 1 s (desglose calculado en la misma transacción).
- **RNF-P6-02**: Concurrency: dos confirmaciones simultáneas del mismo insumo → nunca stock negativo (row-level locking).
- **RNF-P6-03**: Historial inmutable: el desglose guardado en el pedido no cambia si después edito la receta (snapshot de precios).
- **RNF-P6-04**: A11y: tabla de desglose con `scope` en headers; estados con texto (no solo color).
- **RNF-P6-05**: Mobile: wizard de creación en pasos (Cliente → Productos → Resumen) para no tener scroll infinito.
- **RNF-P6-06**: Export CSV de hasta 500 pedidos < 5 s (streaming; sin cargar el conjunto completo en memoria).
- **RNF-P6-07**: Cero credenciales de Mercado Pago en el frontend ni en el repo (`security.md` #1–3, #6); el portal solo consume los endpoints propios de la API.
- **RNF-P6-08**: Webhook de pago: idempotente (dedupe por id de pago), tolerante a reintentos del proveedor y a estados que llegan desordenados; el efecto sobre `paid` es mono-tónico (`false → true` nunca vuelve atrás por replay). Antes de marcar `paid=true` se aplica la validación de `get_payment` (`external_reference`, `transaction_amount` sin tolerancia, `currency_id`) de RF-P6-13; si no coincide no marca `paid`, registra la discrepancia y responde 200. Casos de test: monto menor, pedido ajeno, moneda distinta.

## Tareas
- [ ] API: CRUD `/orders` (list con filtros `status,paid`; create; update; `PATCH /orders/{id}/status`)
- [ ] API: `PATCH /orders/{id}/paid` · `GET /orders/weekly` · `GET /orders/export` (CSV, filtros from/to/status/paid)
- [ ] API: `POST /orders/{id}/whatsapp-link` (genera + registra)
- [ ] API: `POST/GET /orders/{id}/payment` + `POST /webhooks/mercadopago` (firma + idempotencia + estados) sobre `CheckoutProvider` con `MockCheckoutProvider` (RF-P6-13)
- [ ] Domain: `payment_method`/`payment_reference`/`paid_at` en `order`; regla de marcado de `paid` (manual o webhook, nada más)
- [ ] Domain: `order`, `order_item`, snapshot de precios, máquina de estados, reglas de descuento atómico, flag `paid` (independiente), resumen semanal (agregación)
- [ ] Data: transacción con `SELECT … FOR UPDATE` en stock; tabla de snapshot de desglose
- [ ] Web: lista de pedidos (estado, **pago**, cliente, total, fecha) con búsqueda + filtro "Sin pagar" + contador
- [ ] Web: banner de corte (`Alert.Root` warning) cuando `order_window_open=false` (lecto de `/tenant/order-window` en el shell)
- [ ] Web: vista resumen semanal (tabla + totales) + CTA "Exportar CSV"
- [ ] Web: wizard de creación (3 pasos, reutiliza wizard de presupuesto en componentes)
- [ ] Web: detalle de pedido con desglose (tabla insumos + bloques de cálculo)
- [ ] Web: control de margen override (input % con "usar default" para resetear)
- [ ] Web: CTA "Le paso $X" (wa.me) + toast "Enviado"
- [ ] Web: botones de transición de estado (confirmar/entregar/cancelar)
- [ ] Tests: pytest de descuento atómico (caso: stock insuficiente → 409 + sin cambios), snapshot inmutable, máquina de estados; Vitest del wizard
- [ ] GA4: `order_created`, `order_confirmed`, `order_paid`, `weekly_export`, `whatsapp_price_sent`, `payment_started`, `payment_completed`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Tabs` (wizard pasos), `Card` (item de pedido con stepper de cantidad), `Table` (desglose), `Badge` (estados), `Button` (CTA primary "Le paso $X"), `Field.Root`.
- Detalle: bloques de cálculo como filas de tabla destacadas: Total gastos / Trabajo / Ganancia (X%) / **Precio final**.
- CTA único por estado: nuevo → "Le paso $X"; confirmado → "Marcar entregado"; entregado → (sin CTA).
- Tokens: estado nuevo = neutral, confirmado = success, entregado = muted, cancelado = danger. Pago: badge `Pagado` success / `Sin pagar` warning / `Cobrar en la entrega` (neutral con ícono de efectivo) — texto, no solo color.
- Banner de corte: `Alert.Root` warning con el mensaje del tenant + fecha de reapertura; CTA de creación deshabilitado.

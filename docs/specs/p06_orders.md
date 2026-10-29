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
- [ ] Inicio de pago Mercado Pago con `Idempotency-Key` en un pedido `nuevo`: devuelve `reference` determinístico + `checkout_url`; re-intento con la misma key devuelve la misma respuesta guardada (ni un segundo pago, ni error).
- [ ] Webhook simulado `approved` (firma válida) marca `paid` + `paid_at` + `payment_reference` en una transacción; el replay y los estados desordenados no revierten ni duplican el efecto; un pedido `cash` permanece `paid=false` hasta que lo marco yo.

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
- **RF-P6-12**: Método de pago: `payment_method ∈ {mercadopago, cash}` (requerido en creación desde el portal; default `cash` en creación desde el panel admin) + `payment_reference?` (id del pago del proveedor, server-managed) + `paid_at?` (timestamp server-managed) + `payment_status ∈ {pending, approved, rejected, failed}?` (estado del pago del proveedor, server-managed: se setea a `pending` al iniciar el pago (RF-P6-13) y luego solo por webhook; en pedidos `cash` es **siempre `null`**). `payment_method` es inmutable tras la confirmación del pedido. `paid` (RF-P6-10) es **monótono** `false → true` y solo lo setea el marcado manual de la dueña (RF-P6-10) o el webhook `approved` (RF-P6-13); ninguna otra vía (ni UI de portal, ni re-intento de API) lo modifica. (UC-10/11)
- **RF-P6-13**: Mercado Pago (contratos, safe mode de la skill `mercadopago-integration`):
  - **Contrato agnóstico**: protocolo Python `CheckoutProvider` (puro, sin dependencias de proveedor): `create_payment(order) → {reference, checkout_url}`, `get_payment(reference) → {status}`, `verify_webhook(payload) → payload verificado | None`. `MockCheckoutProvider` es la **única** implementación en v1: referencia determinística `mock_<order_id>`; estado determinístico derivado de la referencia (último dígito: `0` → `rejected`, `1` → `pending`, otro → `approved`); firma determinística (HMAC con constante de pruebas hardcodeada, **sin env ni credenciales**); cero I/O, sin red, sin aleatoriedad, sin reloj (salvo timestamps del pedido). Marcar `TODO(live)` donde el proveedor real entraría.
  - **Endpoints**: `POST /orders/{id}/payment` (solo `status=nuevo` + `payment_method=mercadopago`; `Idempotency-Key` **requerida**) → `{reference, checkout_url}`: re-intento con la misma key → misma respuesta guardada (200); otra key con `payment_status=pending` → 409 `payment_in_progress`; `payment_status` terminal → 422 `payment_finalized`; `payment_method=cash` → 422 `payment_method_not_mercadopago`; `status ≠ nuevo` → 409 `order_not_payable`; pedido de otro tenant → 404 anti-sondeo. `GET /orders/{id}/payment` → `{status, paid, payment_reference?, updated_at?}` (polling del portal; `status` = `payment_status`, `null` si no se inició pago; 404 anti-sondeo).
  - **Webhook** `POST /webhooks/mercadopago` (público, **sin auth por cookie**: solo firma): (1) validar firma vía `verify_webhook` **ANTES de cualquier efecto** → 401 si falla o payload no parseable tras verificación → 422; (2) dedupe por id de pago del proveedor en tabla persistente `payment_event` (únicos; replay → 200 `{"ok":true}` sin efecto); (3) estados desordenados tolerados por prioridad `approved > rejected = failed > pending`: `pending` nunca sobreescribe terminal; `approved` se aplica como máximo una vez (guard `WHERE paid=false`); `rejected`/`failed` son intercambiables y **nunca revierten** `paid`; (4) `approved` → `paid=true` + `paid_at=now` + `payment_reference` + `payment_status=approved` en **una sola transacción**; (5) con firma válida, responder siempre 200 `{"ok":true}` (incluye dedupe), para no hacer que el proveedor re-intente. (UC-10)
  - **Safe mode** (límites de la skill): sin instalar/importar SDK live, sin variables de entorno `MP_*`, sin creación de sesiones reales, sin procesamiento de callbacks en vivo. El rollout live requiere la sección Security Handoff (RF-P6-14).
- **RF-P6-14**: Efectivo en la entrega: `payment_method=cash` → `payment_status=null`, el pedido permanece `paid=false` con badge "Cobrar en la entrega" (lista y detalle, texto no solo color); la dueña lo marca con el toggle de RF-P6-10 (`PATCH /orders/{id}/paid`); `POST /orders/{id}/payment` sobre un pedido `cash` → 422 `payment_method_not_mercadopago`. **Security Handoff** (requisito de la skill para el rollout live, fuera de esta specs): credenciales `MP_ACCESS_TOKEN`/`MP_WEBHOOK_SECRET` solo en env del backend; firma HMAC del webhook validada antes de cualquier efecto; rate limit en el webhook; validación de montos y auditoría de transacciones; no se prescribe aquí SDK live ni creación de sesiones reales del proveedor.
- **RF-P6-11**: Resumen semanal: semana natural (Lun–Dom) con pedidos `confirmado`/`entregado` (cliente, ítems, total, pago), totales (`amount`, `paid`, `unpaid`) + export CSV `GET /orders/export` (y `GET /budgets/export` en F3). (UC-08)

## Requerimientos no funcionales
- **RNF-P6-01**: Crear pedido con 10 ítems < 1 s (desglose calculado en la misma transacción).
- **RNF-P6-02**: Concurrency: dos confirmaciones simultáneas del mismo insumo → nunca stock negativo (row-level locking).
- **RNF-P6-03**: Historial inmutable: el desglose guardado en el pedido no cambia si después edito la receta (snapshot de precios).
- **RNF-P6-04**: A11y: tabla de desglose con `scope` en headers; estados con texto (no solo color).
- **RNF-P6-05**: Mobile: wizard de creación en pasos (Cliente → Productos → Resumen) para no tener scroll infinito.
- **RNF-P6-06**: Export CSV de hasta 500 pedidos < 5 s (streaming; sin cargar el conjunto completo en memoria).
- **RNF-P6-07**: Cero credenciales de Mercado Pago en el frontend ni en el repo (`security.md` #1–3, #6); el portal solo consume los endpoints propios de la API.
- **RNF-P6-08**: Webhook de pago: idempotente (dedupe por id de pago), tolerante a reintentos del proveedor y a estados que llegan desordenados; el efecto sobre `paid` es mono-tónico (`false → true` nunca vuelve atrás por replay).
- **RNF-P6-09**: Safe mode verificable (checklist de `references/testing.md` de la skill): el repo no importa ningún SDK de pagos (`mercadopago`, `@mercadopago/sdk-js` u otro), no declara ni lee env de credenciales de gateway (`MP_ACCESS_TOKEN`, etc.) y no existe ruta que llame a una API de pago externa; `MockCheckoutProvider` es determinístico (misma entrada → misma salida; verificable por test, sin aleatoriedad/reloj/rede).
- **RNF-P6-10**: Concurrency de pago: el dedupe del webhook es **persistente** (sobrevive a reinicios; no solo en memoria) y O(1) (índice único sobre el id de pago); el efecto sobre `paid` se aplica con guard de fila (`WHERE paid=false`), de modo que un `approved` concurrente con un marcado manual → ambos consistentes, uno solo escribe `paid_at`; `POST /orders/{id}/payment` concurrente con distintas keys → exactamente un `pending` (el otro → 409).

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

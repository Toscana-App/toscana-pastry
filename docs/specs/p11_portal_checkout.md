# P11 — Portal self-service + checkout e2e

## Contexto
El portal es la sección self-service de la app (Next.js, raíz) para los roles `negocio` y `cliente`, sobre el panel de administración existente (`/admin/**`, rol `admin`). **Precondición**: sistema de roles de 3 vías con precios duales por audiencia (`odd/tasks/roles-dual-pricing.md`) — el portal nunca expone precios de la audiencia ajena (fuga = 403, no solo ocultación). Levanta la decisión #7 de `master_plan.md` ("sin portal self-service") por decisión del owner (2026-10-25, ver `odd/tasks/checkout-portal-e2e.md` S5); la restricción de sockets se mantiene. El flujo de checkout sigue el patrón del proyecto de referencia `toscana-demo`: 5 pasos (contacto → dirección → entrega → pago → revisión).

## User story
"Como cliente particular o negocio (dietética/kiosco), quiero ver la lista de precios de mi audiencia, armar un carrito, completar un checkout de 5 pasos, pagar con Mercado Pago o en efectivo en la entrega, y seguir mis pedidos, sin depender de que la dueña cargue cada pedido."

## Casos de uso
| UC | Actor | Descripción |
|---|---|---|
| UC-01 Acceso al portal | negocio / cliente | Login (magic link) → redirect a portal; `admin` → `/admin` |
| UC-02 Catálogo de mi audiencia | negocio / cliente | Listado/detalle con precio de su audiencia y tags de restricción |
| UC-03 Carrito | negocio / cliente | Agregar/quitar/cantidad, cupón, persistencia por usuario |
| UC-04 Paso 1 Contacto | negocio / cliente | Datos de contacto precargados (usuario registrado) |
| UC-05 Paso 2 Dirección | negocio / cliente | Elegir del libro o crear nueva dirección de entrega |
| UC-06 Paso 3 Entrega | negocio / cliente | Fecha de entrega + modalidad (delivery / retiro) |
| UC-07 Paso 4 Pago | negocio / cliente | Mercado Pago o efectivo en la entrega |
| UC-08 Paso 5 Revisar y confirmar | negocio / cliente | Confirmar pedido; 409 si la ventana de pedidos está cerrada |
| UC-09 Pago Mercado Pago | negocio / cliente | Redirect a checkout del proveedor → webhook → `paid` automático |
| UC-10 Pago efectivo | negocio / cliente (dueña) | `paid=false` hasta que la dueña lo marca en P6 |
| UC-11 Mis pedidos | negocio / cliente | Listado + detalle de sus pedidos (solo lectura de estados) |
| UC-12 Libro de direcciones | negocio / cliente | CRUD de direcciones + dirección por defecto |
| UC-13 Formulario de contacto (lead) | público | Captura de lead `consumer`/`business` desde landing |
| UC-14 Cupones | negocio / cliente + admin | Código de descuento aplicado en el checkout; ABM en admin |
| UC-15 Gestión de leads | admin | Lista, búsqueda, marcar leídos |

## Requerimientos funcionales
- **RF-P11-01**: Acceso por rol: el portal (`/`) solo para `negocio` y `cliente`; `admin` → redirect a `/admin`; sin sesión → `/login` con redirect de vuelta. Todos los listados/detalles de productos sirven **solo el precio de la audiencia del rol** (precios duales; ver spec de roles). (UC-01/02)
- **RF-P11-02**: Checkout de 5 pasos, uno por pantalla, con navegación adelante/atrás y resumen lateral: 1 Contacto → 2 Dirección → 3 Entrega → 4 Pago → 5 Revisar y confirmar. El pedido se crea **solo en el paso 5** (`POST /orders` con `items`, `date`, `pickup`, `delivery_address`, `payment_method`, `coupon_code?`). Para `negocio`/`cliente`, `customer_id` se deriva de la sesión (422 si viene en el body), `margin_pct` no es aceptado (422) y el precio se calcula siempre en servidor con la audiencia del rol; `customer_id` y `margin_pct` quedan solo para `admin`. `delivery_address` es requerida solo en delivery (`pickup=false`). `POST /orders` exige `Idempotency-Key`: misma clave → mismo pedido (sin consumo duplicado de cupón); misma clave con body distinto → 422; el alcance es por usuario y la clave expira a las 24 h (TTL). Sin guest checkout en v1: se requiere cuenta. (UC-04…08)
- **RF-P11-03**: Carrito server-side por usuario autenticado (entidad `cart_items`: `product_id`, `qty`, `unit_price_snapshot?` informativo): máx. 50 líneas, `qty` 1–999; el precio mostrado se deriva del motor en cada lectura según la audiencia (nunca se persiste el precio como fuente). (UC-03)
- **RF-P11-04**: Paso 1 Contacto: precargado desde el usuario registrado (nombre, teléfono, email); los cambios actualizan al cliente. Teléfono normalizado E.164 (+54 default). (UC-04)
- **RF-P11-05**: Paso 2 Dirección: elegir del libro de direcciones (RF-P11-09) o crear una nueva (se guarda en el libro). Modalidad **retiro** (`pickup`) deshabilita la dirección (no requerida); modal **delivery** la requiere. (UC-05)
- **RF-P11-06**: Paso 3 Entrega: `date` ≥ hoy + `min_lead_days` del tenant (default 2); modalidad `delivery | pickup` (default `delivery`). Sin costo de envío en v1 (ver "por confirmar"). (UC-06)
- **RF-P11-07**: Paso 4 Pago: `payment_method ∈ {mercadopago, cash}` (semántica completa en `p06_orders.md` RF-P6-12…14). (UC-07)
- **RF-P11-08**: Paso 5 Revisar y confirmar: ítems con tags de restricción, dirección (si aplica), fecha, modalidad, método de pago, cupón aplicado, total. Confirmar → `POST /orders`; si `order_window_open=false` → 409 `{detail: order_window_closed, message}` (RF-P6-09) → banner con el mensaje del tenant y el CTA queda deshabilitado. Éxito → pantalla de confirmación con código de pedido. (UC-08)
- **RF-P11-09**: Libro de direcciones por cliente: `GET/POST/PATCH/DELETE /customers/me/addresses`; máx. 5 por cliente; `is_default` (exactamente 1; al borrar la default, la primera restante pasa a default). Esquema: `street_line_1*`, `street_line_2?`, `city?`, `postal_code?`, `province?`, `phone?`. El checkout precarga la default; el presupuesto (P7) la usa como sugerencia de `delivery_address`. (UC-12)
- **RF-P11-10**: Pago Mercado Pago (flujo portal): secuencia: confirmar paso 5 → `POST /orders` (devuelve `{order, breakdown}`) → `POST /orders/{id}/payment` (vía `CheckoutProvider`, interfaz agnóstica + `MockCheckoutProvider` de referencia; ver p06 RF-P6-13; devuelve `{reference, checkout_url}`) → redirect del navegador a `checkout_url`. Si el pago falla, se abandona o el usuario vuelve atrás, el pedido queda `status=nuevo` y `paid=false`, y el pago se reintenta sobre el mismo pedido con `POST /orders/{id}/payment` (sin crear un pedido nuevo). Mientras el pago está pendiente, "Mis pedidos" muestra el pedido con estado de pago "Pendiente de pago" y la acción de reintentar. La pantalla de confirmación consulta `GET /orders/{id}/payment` (polling ≤ 5 s) para el estado (`pending → approved | rejected | failed`) mientras el webhook (RF-P6-13) marca `paid`. Un pago pendiente expira a las 24 h: el sistema cancela automáticamente el pedido, notifica a la dueña y libera el uso del cupón. (UC-09)
- **RF-P11-11**: Efectivo en la entrega: `payment_method=cash` → pedido `paid=false` con badge "Cobrar en la entrega" visible en P6 (lista y detalle); la dueña lo marca con el toggle existente (`PATCH /orders/{id}/paid`, RF-P6-10). El portal muestra "Pagar en efectivo en la entrega" como estado de pago del pedido. (UC-10)
- **RF-P11-12**: Mis pedidos: `GET /orders/mine` (paginado, solo pedidos del `customer_id` del usuario; 404-style para pedidos ajenos) y `GET /orders/mine/{code}` (detalle: estado, pago, fecha/dirección de entrega, ítems con total — sin costos internos). Solo lectura de estados: el portal no transiciona, cancela ni edita pedidos en v1. (UC-11)
- **RF-P11-13**: Leads (captura de contacto): formulario público (hCaptcha + rate limit, sin sesión): `{name*, email*, phone?, customer_type ∈ {consumer, business}*, business_name?, location?, message*}` → entidad `lead` con `read` (default false). Admin: `GET /leads?q,read,customer_type,page,page_size`, `PATCH /leads/{id}/read {read}`, `POST /leads/read-all`. GA4: `lead_submitted` (consent-gated). (UC-13/15)
- **RF-P11-14**: Cupones: entidad `coupon` por tenant: `code*` (único, case-insensitive), `type ∈ {percent, fixed}`, `value` (Pct 0–100 o Money ≥ 0), `valid_from?`, `valid_until?`, `max_uses?`, `uses` (contador), `status ∈ {active, paused}` (default active). ABM admin-only `POST/PATCH/DELETE /coupons` (delete/409 si usado en pedidos). En el carrito: `POST /cart/coupon {code}` → validaciones (existe, activo, vigencia, `max_uses`) con 422 y razón explícita; 1 cupón por carrito; `DELETE /cart/coupon`. `uses` se incrementa de forma atómica en la misma transacción que crea el pedido, con `UPDATE ... SET uses = uses + 1 WHERE uses < max_uses` (0 filas → 422 `max_uses`); al cancelar el pedido se libera el uso (`uses` se decrementa). `discount_amount = min(descuento, total)`; si el total resulta 0 solo se permite `cash`/sin pago online (no `mercadopago`). El descuento se recalcula siempre en servidor al confirmar (`POST /orders` con `coupon_code` es la única fuente; el carrito es informativo). Al confirmar, el pedido snapshotea `coupon_code` + `discount_amount` (calculado sobre el total de la audiencia, antes de redondeo; el redondeo del motor aplica sobre el total post-descuento). (UC-14)
- **RF-P11-15**: Eventos GA4 (consent-gated): `checkout_started`, `checkout_step_changed`, `order_placed`, `payment_started`, `payment_completed`, `lead_submitted`, `address_created`, `coupon_applied`. (UC-03…14)

## Requerimientos no funcionales
- **RNF-P11-01**: Cero credenciales de Mercado Pago en el frontend ni en el repo (`security.md` #1–3, #6); el portal solo consume endpoints propios de la API.
- **RNF-P11-02**: El webhook de pago es idempotente y tolera reintentos y estados desordenados del proveedor (el estado final prevalece por prioridad de estado MP).
- **RNF-P11-03**: Carrito, checkout y listado comparten el mismo motor de precios y la misma fuente de precios por audiencia (sin segunda vía de cálculo).
- **RNF-P11-04**: Portal responsive mobile-first + WCAG AA (tokens y auditoría de la Fase 4).
- **RNF-P11-05**: Proveedor de pago mock/no configurado: degradación explícita ("Pago online no disponible" en el paso 4); el efectivo siempre está disponible.
- **RNF-P11-06**: RLS por tenant y por audiencia en `orders/mine`, carrito, cupones y leads (404 anti-sondeo a entidades ajenas, `security.md` #4/#7).

## Tareas
- [ ] Domain: `payment_method`/pagos (p06), `cart_items`, `coupon`, `lead`, `customer_address`; motor: descuento de cupón + redondeo.
- [ ] API FASE 5: portal (`orders/mine`, carrito + cupón), `customers/me/addresses`, `coupons` (admin), `leads` (público + admin), `orders/{id}/payment` + webhook Mercado Pago.
- [ ] Frontend: shell del portal por rol, catálogo de audiencia, carrito, checkout 5 pasos, confirmación + polling de pago, mis pedidos, libro de direcciones, formulario de contacto, ABM de cupones y leads en admin.
- [ ] Tests: RNF-P11-06 (cross-tenant/audencia), idempotencia del webhook, cupones (vigencia, max_uses, percent/fixed), lead con hCaptcha, carrito (límites).

## UI (Chakra v3 + DESIGN.md)
- **Shell del portal**: tab bar (Inicio · Mis pedidos · Carrito · Cuenta) + CTA "Nuevo pedido"; navbar con rol visible; sin acceso a `/admin`.
- **Checkout**: stepper de 5 pasos (progreso visible, back permitido), resumen lateral (cards surface outline, sin sombras), errores inline con `aria-describedby` (zod + react-hook-form).
- **Pago**: tarjetas de selección (Mercado Pago / Efectivo) con estado `pending` (spinner + "Esperando confirmación…") y estados finales `approved` (success) / `rejected|failed` (danger + motivo) sobre el polling.
- **Mis pedidos**: tabla mobile-first (cards en móvil) con badges de estado y pago (texto, no solo color); detalle con ítems + tags de restricción.
- **Leads (admin)**: tabla con badges `consumer`/`business`, `read` (punto), acciones "Marcar leído" / "Marcar todos leídos".
- **Cupones (admin)**: lista + dialog de edición; estados `active`/`paused` con switch; contador de usos.
- CTA único por pantalla (gradiente blue-400→500); touch targets ≥ 44 px.

## Por confirmar con Gaspar
1. **Costo de envío**: v1 no lo cobra (decisión actual). Si se cobra, `delivery_fee` por tenant entra en el desglose del pedido.
2. **Cupones**: ¿v1 con `percent` y `fixed` alcanza, o también "segundo ítem a mitad de precio"? (Spec actual: percent + fixed).
3. **Leads**: ¿el formulario de contacto se publica en la landing pública (requiere `POST /leads` en la allow-list de `security.md` #6) o solo dentro del portal?
4. **Mercado Pago live**: el rollout con proveedor real es un trabajo separado (Security Handoff, p06 RF-P6-14); la v1 corre con mock + efectivo.

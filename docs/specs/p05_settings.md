# P5 — Configuración (costos y márgenes)
Módulo: `web/modules/settings` · Ruta: `/configuracion` · Fase: **1**

## Contexto
Reglas de precio por defecto del negocio (verificado en screenshot): "Tus costos y márgenes". Es la configuración de tenant que alimenta el motor de precio de todos los productos.

## User story
> Como **repostera**, quiero **definir mis costos y márgenes una sola vez**, para **que todos mis productos se precien con mis reglas sin tocarlos uno por uno**.

**Criterios de aceptación**
- [ ] Configuro: valor de mi hora, margen %, redondeo, e incluir/sin incluir mano de obra, gas/energía (%) y merma (%).
- [ ] Guardo y veo confirmación; los precios de productos se recalculan.
- [ ] Si mi margen es 30% y cambio a 40%, veo cuántos productos se ven afectados (contador de recálculo).
- [ ] Valores inválidos (margen > 100, hora negativa) no se guardan: error inline.
- [ ] Cierro los pedidos con fecha de reapertura y un mensaje; en Pedidos (P6) veo el banner y no puedo crear pedidos.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver mi configuración | Repostera | Abre Configuración → valores actuales |
| UC-02 Editar márgenes | Repostera | Cambia campos → guardar → recálculo global |
| UC-03 Ver opciones de recargo urgencia | Repostera | Ve el recargo sugerido % (usado en P6) |
| UC-04 Restaurar valores por defecto | Repostera | "Restaurar" → valores default del sistema |
| UC-05 Cerrar/aperturar pedidos | Repostera | Toggle + fecha de reapertura + mensaje → guardado; el banner aparece en Pedidos (P6) |

## Requerimientos funcionales
- **RF-P5-01**: Campos: `hourly_rate*`, `margin_pct` (0–100), `round_step` (> 0), `include_labor` (bool), `include_gas` (bool), `gas_pct` (0–100, requiere include_gas), `include_waste` (bool), `waste_pct` (0–100, requiere include_waste), `urgent_surcharge_pct`. (UC-01/02)
- **RF-P5-02**: Guardado atómico: toda la config o nada; validación completa antes de persistir. (UC-02)
- **RF-P5-03**: Al guardar, dispara recálculo asíncrono de todos los productos afectados y expone progreso/contador. (UC-02)
- **RF-P5-04**: Valores por defecto del sistema (hora $3.000, margen 30%, redondeo 100, toggles ON, gas 3%, merma 3%, urgencia 20%). (UC-04)
- **RF-P5-05**: "Restaurar por defecto" (sin borrar datos: solo reconfigura). (UC-04)
- **RF-P5-06**: Los toggles deshabilitan visualmente su % asociado (campo inactivo). (UC-01)
- **RF-P5-07**: Corte de pedidos (ventana de pedidos): `order_window_open` (bool, default true), `order_window_reopens_at` (datetime, requerido si se cierra sin abrir), `order_window_message` (≤ 200 chars). Cerrada → P6 muestra banner con el mensaje y bloquea la creación. Endpoint dedicado `GET/PATCH /tenant/order-window` (autenticado; v1 no tiene catálogo público). (UC-05)

## Requerimientos no funcionales
- **RNF-P5-01**: Recálculo global de hasta 500 productos en < 10 s (tarea en cola, con notificación de finalización).
- **RNF-P5-02**: La página carga < 500 ms (1 solo endpoint GET).
- **RNF-P5-03**: A11y: toggles con `aria-pressed`, labels asociados, grupos con `fieldset/legend`.
- **RNF-P5-04**: Mobile: secciones apiladas; sticky CTA "Guardar".

## Tareas
- [ ] API: `GET /tenant/settings`, `PUT /tenant/settings` (validación Pydantic completa)
- [ ] API: `GET /tenant/order-window` + `PATCH /tenant/order-window` (corte de pedidos; cerrar sin `reopens_at` → 422 con sugerencia; `message` ≤ 200 chars)
- [ ] API: job de recálculo (cola) + `GET /tenant/recalculation-status`
- [ ] Domain: entidad `tenant_settings`, validaciones de rangos
- [ ] Web: form con secciones (Horas y margen / Redondeo / Componentes opcionales / Urgencia)
- [ ] Web: toggles con campos dependientes deshabilitados
- [ ] Web: estado de recálculo en curso (badge/contador) y toast de finalización
- [ ] Tests: pytest de validaciones (margen 101 → 422, toggle OFF con % → 422); Vitest de dependencias de toggles
- [ ] GA4: `settings_saved`, `order_window_changed`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Field.Root`, `InputNumber`, `Switch` (toggles), `NumberInput`, `Button`, `Stack`, `Alert` (confirmación).
- Layout: secciones con headings H3 (medium 500) + párrafos de ayuda (muted); grupos con `Fieldset`.
- CTA único: **Guardar cambios** (sticky, safe-area).
- Tokens: estados success al guardar (toast), warning para "recalculando…".

---

# P5-CC — Configuración de la calculadora de costos (rol administrador)

> Actualización derivada de la implementación de la **calculadora de costos** refactorizada a partir del código funcionando `E:/toscana/calculadora-costos-toscana` (app Base44). **Alcance exclusivo del rol administrador.** El módulo legacy de P5 (`/tenant/settings`, markup, gas/merma) **queda intacto y coexiste**: la calculadora tiene su propia configuración con otro modelo de precio (margen sobre precio final + descuento + impuesto + redondeo).

## Contexto
En la app de origen, la configuración de la calculadora (SettingsPage) tiene 5 pestañas: **General** (nombre del negocio, moneda, márgenes/impuesto por defecto y modo de redondeo), **Categorías de materiales**, **Categorías de productos**, **Proveedores** y **Costos por defecto**. Todo es admin-only.

## User story
> Como **administrador**, quiero **configurar la moneda, los márgenes/impuesto por defecto, el redondeo y el catálogo de soporte (categorías, proveedores, costos por defecto)**, para **que la calculadora de costos precie mis productos con mis reglas**.

**Criterios de aceptación**
- [ ] Veo y edito los valores generales: nombre del negocio, nombre/símbolo de moneda, margen por defecto (30), descuento por defecto (0), impuesto por defecto (19) y modo de redondeo (`none` por defecto).
- [ ] Guardo la configuración general y recibo confirmación; el PUT es reemplazo completo y atómico.
- [ ] Gestiono con CRUD completo: categorías de materiales, categorías de productos, proveedores y costos por defecto.
- [ ] Todo el ABM exige rol administrador (no-admin → 403).
- [ ] El motor de precio de la calculadora (CC-04) usa estos valores por defecto para productos nuevos.

## Requerimientos funcionales
- **RF-P5CC-01**: Configuración general (recurso singleton): `business_name` (string 1–120), `main_currency_name` (string 1–40), `main_currency_symbol` (string 1–8), `default_margin_percent` (0–100, default `30`), `default_discount_percent` (0–100, default `0`), `default_tax_percent` (0–100, default `19`), `rounding_mode` (allow-list `none | integer | multiple_10 | commercial_99`, default `none`).
- **RF-P5CC-02**: `GET` devuelve la fila persistida o los defaults del sistema (nunca 404). `PUT` valida todo el payload (`extra="forbid"`) y persiste atómicamente (upsert de una sola fila).
- **RF-P5CC-03**: ABM **categorías de materiales**: `name*` (1–80, único), `description?` (≤200). List/create/get/patch/delete; delete con hijos (materiales que la referencian) → 409.
- **RF-P5CC-04**: ABM **categorías de productos**: mismos campos y reglas que RF-P5CC-03.
- **RF-P5CC-05**: ABM **proveedores**: `name*` (1–120), `contact_name?` (≤120), `phone?` (≤30), `email?` (formato email, ≤120), `notes?` (≤500). Mismas reglas de delete con hijos → 409.
- **RF-P5CC-06**: ABM **costos por defecto**: `name*` (1–120), `type` (allow-list `labor | extra_cost`), `default_unit_cost_or_rate` (Money ≥ 0), `default_quantity_or_minutes` (Qty ≥ 0), `status` (`active` | `inactive`, default `active`).
- **RF-P5CC-07**: Búsqueda `?q` case/acento-insensitive en las 4 colecciones; paginación `?page&page_size` (default 50, max 100).
- **RF-P5CC-08**: Solo rol administrador: todos los endpoints de este módulo → `403` para usuarios no admin. Los datos de costos **nunca** se exponen fuera del tenant (security #17).

## Requerimientos no funcionales
- **RNF-P5CC-01**: Money con `Decimal` + `ROUND_HALF_UP` (convención `Money` del proyecto); float nunca toca montos.
- **RNF-P5CC-02**: Todos los endpoints async; esquemas Pydantic v2 con `extra="forbid"`.
- **RNF-P5CC-03**: La página de configuración carga < 500 ms (1 GET por pestaña).

## API (nuevo namespace `/api/v1/calc`) — ver `api_endpoints.md` §FASE CC
- `GET/PUT /api/v1/calc/settings`
- `GET|POST /api/v1/calc/material-categories`, `GET|PATCH|DELETE /api/v1/calc/material-categories/{id}`
- `GET|POST /api/v1/calc/product-categories`, `GET|PATCH|DELETE /api/v1/calc/product-categories/{id}`
- `GET|POST /api/v1/calc/suppliers`, `GET|PATCH|DELETE /api/v1/calc/suppliers/{id}`
- `GET|POST /api/v1/calc/default-costs`, `GET|PATCH|DELETE /api/v1/calc/default-costs/{id}`

## UI (Chakra v3 + DESIGN.md, rol admin)
- Componentes: `Tabs.Root` (5 pestañas), `Field.Root`, `Input`, `Select.Root` (rounding_mode), `Table`, `Dialog` (confirmar borrado), `Button`, `EmptyState`.
- Layout: encabezado "Configuración de la calculadora" + tabs; lista de cards en cada ABM con acciones inline (editar/eliminar).
- Tokens de `.claude/design/DESIGN.md`: cards `surface` con outline 1px (sin shadow), pill buttons, estados success (toast al guardar), danger para borrados.

## Tareas
- [ ] Ver `odd/tasks/cost-calculator.md` (tareas atómicas B1–B6 para backend, F1 para frontend).

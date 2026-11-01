# P2 — Ingredientes (stock)
Módulo: `web/modules/ingredients` · Rutas: `/ingredientes`, `/ingredientes/nuevo`, `/ingredientes/{id}` · Fase: **1**

## Contexto
Lista de insumos con unidad, precio de compra y stock. La app original muestra badges: "8 kg disponibles", "2 kg restantes" (umbral bajo) y estado EMPTY. El stock se descuenta con cada pedido confirmado (Fase 2).

## User story
> Como **repostera**, quiero **saber cuánto tengo de cada insumo y cuánto me cuesta**, para **comprar a tiempo y que los precios de mis productos sean reales**.

**Criterios de aceptación**
- [ ] Veo la lista con: nombre, unidad (kg/g/L/ml/unidades), stock disponible y badge de estado.
- [ ] Busco un ingrediente por nombre en < 200 ms.
- [ ] Agrego un ingrediente (nombre, unidad, precio por unidad, cantidad inicial) en menos de 10 s.
- [ ] Ajusto stock con entradas/salidas (+/−) y cada movimiento queda registrado.
- [ ] Si un ingrediente usado en recetas se elimina, me avisan antes de confirmar.

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver inventario | Repostera | Lista con búsqueda + badges de stock |
| UC-02 Crear ingrediente | Repostera | Formulario → validación → guardado |
| UC-03 Editar ingrediente | Repostera | Cambia nombre/unidad/precio → guardado |
| UC-04 Ajustar stock | Repostera | +/− con motivo (compra/merma/ajuste) → movimiento registrado |
| UC-05 Eliminar ingrediente | Repostera | Si está en recetas → advertencia con impacto; sin recetas → borrado con undo |

## Requerimientos funcionales
- **RF-P2-01**: CRUD de ingredientes: `name`, `unit` (kg\|g\|L\|ml\|unidad), `price_per_unit`, `stock_qty`, `low_stock_threshold`. (UC-01/02/03)
- **RF-P2-02**: Búsqueda por nombre (case/acento-insensitive), debounce 250 ms. (UC-01)
- **RF-P2-03**: Estados de stock: `OK` (disponible), `LOW` (≤ umbral), `EMPTY` (0). Badge con color (success/warning/danger). (UC-01)
- **RF-P2-04**: Movimientos de stock: delta + motivo + referencia (pedido/manual) + timestamp; histórico visible por ingrediente. (UC-04)
- **RF-P2-05**: Bloqueo/advertencia de borrado si el ingrediente participa de recetas activas (muestra cuántas). (UC-05)
- **RF-P2-06**: Formato de moneda y unidades según locale (es-AR): "$3.000 / kg". (UC-01)
- **RF-P2-07**: Importación por lista (pegar texto "harina 0000, 5, 2800") para carga inicial rápida. (UC-02)

## Requerimientos no funcionales
- **RNF-P2-01**: Lista de 500 ingredientes renderizada en < 100 ms (virtualización o paginación 50).
- **RNF-P2-02**: Búsqueda end-to-end < 200 ms en 500 registros (índice de búsqueda en Postgres: `pg_trgm` o `GIN`).
- **RNF-P2-03**: Optimistic UI en ajustes de stock con rollback en error.
- **RNF-P2-04**: A11y: tabla semántica (o lista con `aria-label` por fila), badge legible sin depender solo del color (texto + color).
- **RNF-P2-05**: Mobile-first: fila de ingrediente = card compacta; acciones por swipe o menu (targets ≥ 44px).

## Tareas
- [ ] API: CRUD `/ingredients` (list con `q`, `page`; create; update; delete)
- [ ] API: `POST /ingredients/{id}/stock` (delta, motivo) + `GET /ingredients/{id}/movements`
- [ ] Domain: entidad `ingredient`, regla de estados de stock, `stock_movement`
- [ ] Data: índice `pg_trgm` para búsqueda; tabla `stock_movements`
- [ ] Web: lista con búsqueda (Input con ícono), badges, estado vacío (CTA "Agregar tu primer ingrediente")
- [ ] Web: formulario (create/edit) con zod: nombre requerido, precio > 0, stock ≥ 0, umbral ≥ 0
- [ ] Web: drawer/modal de ajuste de stock (cantidad + motivo)
- [ ] Web: confirmación de borrado con impacto en recetas
- [ ] Web: vista de movimientos del ingrediente (timeline simple)
- [ ] Tests: pytest de estados de stock y movimientos (casos límite: stock 0, umbral 0); Vitest de búsqueda y badges
- [ ] GA4: `ingredient_created`, `stock_adjusted`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Input` (búsqueda con ícono), `Badge` (variantes success/warning/danger), `Card` (ítem), `Drawer` (ajustes), `Field.Root` (form), `Tabs` (detalle: Resumen / Movimientos), `EmptyState` propio.
- Layout: encabezado "Ingredientes" + búsqueda + botón "Nuevo" (ghost con +). Lista de cards.
- CTA único de la pantalla: **Nuevo ingrediente**.
- Tokens: `paper-50` fondo, cards `surface` con outline; badge EMPTY = danger soft; LOW = warning soft; OK = success soft.

---

# P2-CC — Materiales de la calculadora de costos (rol administrador)

> Módulo de la calculadora refactorizada desde `E:/toscana/calculadora-costos-toscana`. **Alcance exclusivo del rol administrador.** No reemplaza el módulo legacy P2 (stock/inventario): el material de la calculadora es un **catálogo de costos** (sin tracking de stock).

## Contexto
En la app de origen, cada material entra con **precio del paquete** y **cantidad por paquete**; el costo por unidad es derivado: `unit_cost = purchase_total_price / package_quantity`. Estados: `active` / `inactive` / `incomplete` (automático cuando falta precio o cantidad por paquete).

## User story
> Como **administrador**, quiero **mantener mi catálogo de materiales con su costo por unidad real**, para **que el costo de cada producto sea el costo que pago de verdad**.

## Requerimientos funcionales
- **RF-P2CC-01**: CRUD de `calc_material`: `name*` (1–120), `internal_code?` (≤40), `category_id?` (FK material-category), `supplier_id?` (FK supplier), `unit_of_measure?` (string ≤20, ej. kg, litro, unidad), `purchase_total_price` (Money ≥ 0), `package_quantity` (Qty > 0), `notes?` (≤500), `status` (`active` | `inactive` | `incomplete`).
- **RF-P2CC-02**: `unit_cost` es **solo-escritura del servidor**: `purchase_total_price / package_quantity` con `Decimal` + `ROUND_HALF_UP` a centavos. Nunca llega del cliente (security #8). `package_quantity` = 0 → 422.
- **RF-P2CC-03**: Si falta `purchase_total_price` o `package_quantity` el material queda `incomplete` (computado por el servidor, no aceptado del cliente).
- **RF-P2CC-04**: **Historial de costos**: cada cambio de `purchase_total_price` que altere `unit_cost` registra `{previous_unit_cost, new_unit_cost, changed_at}`; `GET /calc/materials/{id}/cost-history` paginado.
- **RF-P2CC-05**: Búsqueda `?q` por nombre/código; filtros `?category_id`, `?supplier_id`, `?status`; paginación (default 50, max 100). Delete de material usado en productos → 409 + `{impacted_products}`. Delete de material con historial de costos (append-only) → 409 + `{"detail": "has_cost_history"}`.

## API — ver `api_endpoints.md` §FASE CC
- `GET|POST /api/v1/calc/materials`, `GET|PATCH|DELETE /api/v1/calc/materials/{id}`, `GET /api/v1/calc/materials/{id}/cost-history`

## Tareas
- [ ] Ver `odd/tasks/cost-calculator.md` (tareas atómicas B7–B9, F2–F3).

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

# P3 — Productos (listado)
Módulo: `web/modules/products` (parte list) · Rutas: `/productos` · Fase: **1**

## Contexto
Vitrina de los productos del negocio (tortas, cupcakes, postres) con precios calculados por el motor de costo. En la app original: buscador + chips de categoría + cards con precio.

## User story
> Como **repostera**, quiero **ver todos mis productos con su precio de venta en un vistazo**, para **saber qué tengo y qué le ofrezco a cada cliente**.

**Criterios de aceptación**
- [ ] Veo cards con: nombre, categoría y precio final (derivado del motor, no editable a mano aquí).
- [ ] Filto por categoría (chips: Todas, Tortas, Cupcakes, Postres, …) y busco por nombre.
- [ ] Filto por tag de restricción (Sin gluten, Sin azúcar, …) combinado con categoría; los tags se ven como chips en la card.
- [ ] Tocar una card me lleva al detalle (P4).
- [ ] Con 0 productos: estado vacío con CTA "Crear tu primer producto".
- [ ] El precio se recalcula solo cuando cambio receta o costos (Fase 1).

## Casos de uso
| UC | Actor | Flujo principal |
|---|---|---|
| UC-01 Ver catálogo | Repostera | Lista + chips de categoría + búsqueda |
| UC-02 Buscar producto | Repostera | Búsqueda instantánea por nombre |
| UC-03 Ir al detalle | Repostera | Tap card → P4 |
| UC-04 Crear producto (atajo) | Repostera | "+" → wizard de detalle (P4) |

## Requerimientos funcionales
- **RF-P3-01**: Listado con paginación (20/página) y orden: nombre, precio ↑/↓, reciente. (UC-01)
- **RF-P3-02**: Filtro por categoría (chips, "Todas" por defecto); categorías derivadas de los productos existentes. (UC-01)
- **RF-P3-03**: Búsqueda por nombre (debounce 250 ms), combinable con el filtro de categoría. (UC-02)
- **RF-P3-04**: Precio mostrado = salida del motor de precio (con redondeo aplicado según config del tenant). (UC-05)
- **RF-P3-05**: Indicador visual de precio "desactualizado" (badge) si la receta tiene insumos sin precio. (UC-05)
- **RF-P3-07**: Filtro por tag (chips secundarios, combinables entre sí y con categoría): allow-list sugerida (`sin_gluten`, `sin_lacteos`, `sin_azucar`, `sin_lactosa`, `frutos_secos`, `vegano`, `sugar_free`, `bajo_calorias`) + tags libres; tags derivados de los productos existentes. (UC-01)
- **RF-P3-08**: La card muestra máx. 2 tags + "+n"; el tag completo se ve en el detalle (P4). (UC-03)
- **RF-P3-06**: Estado vacío: ilustración simple + CTA único "Crear tu primer producto". (UC-04)

## Requerimientos no funcionales
- **RNF-P3-01**: Primer paint de la lista < 1 s en 4G; lazy load de páginas.
- **RNF-P3-02**: Grid responsive: 1 col (≤480px), 2 col (≥640px), 3 col (≥900px).
- **RNF-P3-03**: Cards interactivas: hover solo fortalece outline (sin scale/translate); focus visible para teclado.
- **RNF-P3-04**: A11y: chip de categoría como `role=tablist` o botones con `aria-pressed`; lista semántica.

## Tareas
- [ ] API: `GET /products` (q, category, tags, sort, page) → `{items, total}`
- [ ] API: `GET /products/tags` (chips de tags con conteo)
- [ ] Domain: proyección de producto para listado (nombre, categoría, tags, precio_final, stale_flag)
- [ ] Web: grid de cards (nombre, categoría, precio), skeleton de carga
- [ ] Web: chips de categoría + chips de tags + búsqueda combinada
- [ ] Web: estado vacío + CTA
- [ ] Web: link a detalle y a creación
- [ ] Tests: pytest de filtros/orden (casos: sin resultados, categoría vacía); Vitest de chips+búsqueda
- [ ] GA4: `product_viewed`, `product_created`

## UI (Chakra v3 + DESIGN.md)
- Componentes: `Input` búsqueda, `Chip`/`Badge` (categorías, `aria-pressed`), `Card` interactiva, `Stack`, `Skeleton`.
- Layout: header "Productos" + botón "+"; fila de chips (scroll horizontal en mobile, sin hover states activos en touch); grid de cards.
- Card: nombre (text-lg medium), categoría (text-xs muted), tags (chips text-xs, máx. 2 + "+n"), precio (text-lg, tabular-nums). Outline 1px → hover 12% fg. Sin shadow.
- CTA único: **"+ Nuevo producto"** (header) — el resto son navegación.

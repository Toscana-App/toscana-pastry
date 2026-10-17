# Fase 5 — Backend: Catálogo de Productos (P3 + P4)

Resumen técnico de la implementación de la Fase 5 (backend). Especificaciones de
referencia: `p03_products_list.md` y `p4_product_detail.md`.

## Tabla de endpoints

| Método | Ruta | Auth | Descripción |
| --- | --- | --- | --- |
| GET | `/api/v1/products` | auth (customer + admin) | Listado paginado: `q` (insensible a acentos y mayúsculas), `category`, `page` (1..), `page_size` (5..50, def 20). Responde `items[]`, `total`, `page`, `page_size`, `categories[]` (distinct, derivadas de los productos activos — chips del P3). Cada item trae `price_final` / `price_per_serving` como string (Money) o `null` si el producto está incompleto, y `complete` (badge del P3). |
| POST | `/api/v1/products` | admin | Crea producto con su receta. Valida dominio (nombre 2..120, receta ≥1 y ≤30 líneas, insumos existentes y no duplicados, unidades compatibles con la unidad de compra → 400 como `/pricing/preview`, qty > 0). Responde 201 con el detalle completo. |
| GET | `/api/v1/products/{id}` | auth | Detalle (P4) con las 4 pestañas: información, receta (con nombre del insumo, costo de línea, `missing`), preparación (labor_hours = prep_time_min/60) y costos (desglose completo + `price_per_serving`). 200 también para producto incompleto: `complete=false`, `price=null`, `missing_ingredients[]`. |
| PATCH | `/api/v1/products/{id}` | admin | Update parcial (solo campos enviados). Mismas validaciones que POST. |
| DELETE | `/api/v1/products/{id}` | admin | Soft delete (`deleted_at`) SIEMPRE (RF-P4-08): el producto sale del catálogo y los pedidos históricos quedan intactos. Sin pedidos: 204. Con pedidos históricos (Fase 6): 200 con `{impacted_orders}`. Nunca 409 — a diferencia de un insumo en recetas activas, un producto discontinuado debe poder retirarse. |

Contratos de error como Fase 4: 400 con mensaje de dominio, 404 inexistente,
403 rol insuficiente, 422 validación de schema. Money/Qty salen como string en
las responses (RNF-P4-02).

## Decisión: precio derivado en lectura (RF-P3-04)

El precio **nunca se persiste**. Cada GET lo recalcula con el motor de pricing
existente (`domain/pricing.py`): costo de materiales por línea (la receta usa la
unidad del insumo y el motor convierte contra la unidad de compra) → merma →
mano de obra (`labor_hours` derivado de `prep_time_min`) → gas → base → margen
→ redondeo al paso configurado. `price_per_serving = final / servings`
(ROUND_HALF_UP, 2 decimales).

Producto incompleto (insumo borrado, inexistente, o `price_per_unit == 0`) →
`complete=false`, `price=null`, `missing_ingredients[]` con el nombre de cada
insumo faltante (o "Insumo desconocido"), y la línea de receta con
`missing=true` y `line_cost=null`. Es 200, no error: el catálogo muestra el
producto con badge de incompleto.

El módulo `domain/product_price.py` encapsula esa derivación (puro, sin I/O):
`derive_product_price(product, ingredients_by_id, settings) → ProductPrice` y
`line_cost_of_item(item, ingredients_by_id) → Decimal | None`.

## Cambios en el motor de pricing (fix de contrato)

`cost_of_quantity`/`unit_family` aceptaban `l` pero el contrato de ingredientes
debe guardar `L` (unidad de compra de volumen). Agregué `_fold_unit`
(casefold) dentro del motor: `"L"` y `"l"` ahora son equivalentes sin migrar
datos.

## `count_active_recipes` (antes stub `return 0`)

Ahora cuenta líneas reales: `COUNT(recipe_items)` con JOIN a `products`
filtrando `products.deleted_at IS NULL` e `ingredient_id` dado. Con esto el
409 de `DELETE /api/v1/ingredients/{id}` ("insumo en uso") funciona: un
insumo usado por un producto activo bloquea su borrado con
`{"impacted_recipes": n}`; los productos soft-deleted no bloquean.

## ORM / schema

`products`: id, name (indexed), category (indexed), description, prep_time_min,
servings, difficulty, deleted_at. `recipe_items`: id, product_id (FK),
ingredient_id, qty (Text), unit, position (ordena las líneas). Money/qty como
TEXT (RNF-P4-02). Relationship `recipe_items` con `selectin` y cascade
delete-orphan. Sin migración: `Base.metadata.create_all` (SQLite, pre-producción).

## Tests

- `tests/unit/domain/test_products.py`: validaciones de dominio
  (Product/RecipeItem), derivación de precio (completo, incompleto, dedup),
  costo por línea, fix `"L"`.
- `tests/integration/api/test_products_api.py`: RBAC (401/403, customer puede
  leer), create (201 con precio derivado + defaults de settings, 422, 400 por
  insumo desconocido/unidades incompatibles/duplicado, producto incompleto con
  precio 0), list (búsqueda "limon"→"Limón", filtro de categoría, chips de
  categorías, paginación 20/25, `price_final=null` para incompleto), detail
  (desglose completo, 404, líneas `missing`), update (200, parcial, 404, 400),
  delete (204 + 404 posterior), derivación en lectura (cambio de precio del
  insumo cambia el precio del producto), y el 409/204 de borrado de insumo.

## Decisiones de negocio asumidas (sin respuesta del owner)

- Precio de compra 0 = "sin precio" → producto incompleto.
- `labor_hours` derivado de `prep_time_min` (sin override por producto).
- DELETE nunca bloquea: soft delete + `impacted_orders` informativo (200) cuando haya pedidos históricos (Fase 6); 204 si no.

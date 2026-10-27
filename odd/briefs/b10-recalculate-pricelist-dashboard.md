# Brief B10 — recalculate-all, price-list (+CSV), dashboard + sort (backend)

Tarea: B10 de `odd/tasks/cost-calculator.md` (T-B10). Backend solo; la UI (F4) es otra tarea. 4 piezas: recalculate-all, sort en el listado de productos, price-list + export CSV, dashboard.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea B10 (aceptación) + spec S5 (motor/versiones, DONE en B9) + S6 (listado/price-list/dashboard) + S3 (admin-only) + S8 (TDD).
- `docs/specs/p03_products_list.md` §P3-CC → RF-P3CC-01 (sort + item del listado), RF-P3CC-03 (recalculate-all), RF-P3CC-04 (price-list + CSV), RF-P3CC-05 (dashboard).
- `docs/specs/api_endpoints.md` §FASE CC → tabla "CC Productos" líneas ~189–192: `POST /calc/products/recalculate-all`, `GET /calc/products/price-list`, `GET /calc/products/price-list/export`, `GET /calc/dashboard` (rutas, payloads, códigos exactos).
- Decisias del usuario (verbatim en `PREGUNTAS.md`, respetarlas):
  - **D2**: auth patrón B3–B9: GETs con `get_current_user` (401 sin sesión), writes con `require_admin` (403 no-admin).
  - **D4**: material `incomplete` (`unit_cost = None`) → snapshot `0.00`, **sin error** (ya implementado en B9; recalculate-all lo hereda).
  - **D5**: `GET /calc/products` shippeó con orden fijo por nombre; **el sort (`?sort,?dir`) quedó expresamente para B10 si la spec lo exige** — y RF-P3CC-01 + §FASE CC lo exigen. B10 lo implementa.
- **Paridad de referencia (solo semántica, NO se importa)**: `E:/toscana/calculadora-costos-toscana/src/pages/Dashboard.jsx` (qué mide cada métrica: promedios sobre activos, top por precio desc, bottom por margen asc) y `src/pages/PriceList.jsx` (export CSV: `filename = lista_precios.csv`, solo activos, filtros búsqueda/categoría). El motor de precio ya vive en `backend/src/domain/calc_product.py` (B9) — no se toca.

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`. La rama DEBE contener B9: `git merge-base --is-ancestor 183d2ac HEAD` → exit 0. B9 está en `feat/b9-calc-products` (commit `183d2ac`, PR #30). **Crear rama nueva desde esa**: `feat/b10-recalc-pricelist-dashboard` (o similar `feat/b10-*`). B10 NO se apila sobre main.
- **NO commitear ni pushar** — el orquestador lo hace.
- Código/tests en inglés; docstrings en español (convención del repo). No agregar dependencias nuevas.

## TDD: RED primero
Escribí los tests en rojo antes del código. Cobertura del nuevo módulo domain `calc_dashboard` > 90% (S8).

## Alcance (archivos)
| Archivo | Cambio |
|---|---|
| `backend/src/domain/calc_dashboard.py` | NUEVO: `DashboardStats` + `TopByPriceItem`/`BottomByMarginItem` (frozen dataclasses) + `build_dashboard_stats(...)` (función pura) |
| `backend/src/data/repositories/calc/sql_calc_product_repository.py` | APPEND/REFACTOR LOCAL: extraer `_recalculate_one` de `recalculate` (sin commit interno), nuevo `recalculate_all(rounding_mode) -> int`; `list(...)` ampliado con `sort`/`dir` + item con `category_name`; nuevos `list_price_list(...)` y `dashboard_data(rounding_mode)`. `recalculate` individual debe seguir comportándose idéntico (mismos tests B9 verdes). |
| `backend/src/data/repositories/calc/sql_calc_material_repository.py` | SOLO APPEND: `count_by_status() -> dict[str, int]` (status derivado persistido en `calc_materials.status`, B8) |
| `backend/src/api/v1/calc/router.py` | APPEND: 3 endpoints nuevos + `GET /calc/dashboard`. **Cambio documentado D5/RF-P3CC-01 en el endpoint B9 `GET /calc/products`**: params `sort`/`dir` + item enriquecido. **OJO route-order**: `/products/price-list` y `/products/price-list/export` (GET) deben registrarse ANTES de `GET /products/{product_id}` (B9), sino FastAPI resuelve `price-list` como `product_id` → 404. `POST /products/recalculate-all` no colisiona (otro segmento). |
| `backend/src/api/v1/calc/schemas.py` | APPEND: `ProductListItem`/`ProductListResponse` (reemplaza el item actual del listado — sin consumidores frontend aún), `PriceListResponse`, `RecalculateAllResponse`, `DashboardResponse` + items |
| `backend/tests/unit/domain/test_calc_dashboard.py` | NUEVO |
| `backend/tests/integration/api/test_calc_recalculate_all_api.py` | NUEVO |
| `backend/tests/integration/api/test_calc_products_sort_api.py` | NUEVO |
| `backend/tests/integration/api/test_calc_price_list_api.py` | NUEVO |
| `backend/tests/integration/api/test_calc_dashboard_api.py` | NUEVO |

## Reglas de negocio (testeables)

### 1. `recalculate-all` (RF-P3CC-03)
- `recalculate_all(rounding_mode) -> int`: selecciona productos `status="active"` y `deleted_at IS NULL` y aplica a CADA uno lo mismo que el recalculate individual B9:
  1. re-resuelve snapshots de materiales desde `calc_materials` actuales (`material_name`, `unit_of_measure_snapshot`, `unit_cost_snapshot`; **D4: `unit_cost None` → `Decimal("0.00")` sin error**);
  2. recalcula `line_total_cost` de TODAS las líneas (materials/labor/extra, mismo código que B9);
  3. `last_recalculated_at = now(UTC)` **en TODOS los recalculados, aunque el precio no cambie**;
  4. versión append-only **SOLO si el `final_sale_price` recalculado (redondeado) difiere del calculado ANTES de re-resolver**; `version_number = max + 1` **siguiendo la secuencia del producto** (si ya tenía versiones de un recalculate individual, continúa).
- **Transacción única**: un solo `commit()` al final (extraer el cuerpo de `recalculate` a `_recalculate_one(orm, rounding_mode)` que NO comitea; `recalculate` individual llama `_recalculate_one` + `commit` y mantiene comportamiento idéntico — los tests B9 deben seguir verdes sin tocarlos).
- `rounding_mode` = del settings singleton (helper `_settings_defaults` existente en `router.py`); sin fila → `"none"`. Nunca del cliente.
- Devuelve `{recalculated: N}` con N = cantidad de productos recalculados; 0 activos → `{recalculated: 0}` (200, no error).
- Drafts/archived/eliminados: **no tocados** (líneas, `last_recalculated_at` y versiones sin cambios).

### 2. Sort + item enriquecido en `GET /calc/products` (RF-P3CC-01, D5)
- Nuevos query params: `sort: Literal["name","cost","price","margin"] = "name"`, `dir: Literal["asc","desc"] = "asc"` (Literal en Pydantic/FastAPI → inválido → 422).
- Semántica:
  - `name`: orden SQL actual (`func.lower(name)`) — comportamiento B9 intacto por defecto.
  - `margin`: por `margin_percent` **almacenado** (columna String → ordenar como `Decimal` en Python).
  - `cost` / `price`: por `product_total_cost` / `final_sale_price` **calculados por el motor** (`compute_costs` con las líneas y el `rounding_mode` de settings) — nunca por columna (los montos no están persistidos).
  - Implementación: para `margin|cost|price` → fetch de TODAS las filas que matchean (sin offset/limit) + sort en Python + paginación en Python (escala admin, igual que el dashboard). Ties → `name` asc (estable); `dir` invierte solo el campo primario.
- **Item del listado** pasa a incluir (RF-P3CC-01): `id, name, sku, category_name (nullable), status, product_total_cost (str), final_sale_price (str, redondeado), margin_percent, last_recalculated_at`. Es decir, el item B9 (sin costs) se **enriquece** con `category_name` + los 2 montos calculados — mismo esfuerzo que el sort ya exige. (B9 no tenía consumidores frontend; F4 aún no existe.) `total`/`page`/`page_size` y filtros `?q` (nombre Y SKU, accent_fold) / `?category_id` / `?status` sin cambios.

### 3. Price list (RF-P3CC-04)
- `GET /calc/products/price-list`: solo `status="active"` y no eliminados; `?q` (nombre **Y** SKU, `accent_fold`, MISMA query que `list` de B9) + `?category_id?` + `page`/`page_size` (default 50, max `PAGINATION_MAX`=100) → 200 `{items,total,page,page_size}`; **orden fijo por nombre** (D5). Item: `id, name, sku, category_id, category_name (str o null si sin categoría), product_total_cost (str), final_sale_price (str, CON el redondeo del `rounding_mode` de settings), margin_percent`. Los montos se calculan por el motor (líneas + percents del producto), nunca leídos del cliente.
- `GET /calc/products/price-list/export`: `?q,category_id?` (SIN paginación: todo el set filtrado) → 200 `text/csv; charset=utf-8` + `Content-Disposition: attachment; filename="lista_precios.csv"` (paridad legacy). **Header exacto (spec `api_endpoints.md`, no el del legacy)**: `id,name,category,cost,margin_pct,final_price`. Filas en el mismo orden que price-list: `id`, `name`, `category` (nombre de la categoría, cadena vacía si no tiene), `cost` = `product_total_cost` (str 2 decimales, **pre-redondeo** — el costo nunca se redondea), `margin_pct` = `margin_percent` (número), `final_price` = `final_sale_price` redondeado (str). Construir el CSV con el módulo stdlib `csv` sobre `StringIO` (quoting correcto — un nombre con coma debe quedar entre comillas), line terminator `\n`. `category`/`cost`/`final_price` en los mismos valores que el JSON.

### 4. Dashboard (RF-P3CC-05)
Función pura en `domain/calc_dashboard.py` (estilo `domain/calc_product.py`: frozen dataclasses, Decimal, sin I/O):

```
build_dashboard_stats(
    material_status_counts: dict[str, int],     # {"active": N, "incomplete": M}
    product_status_counts: dict[str, int],      # {"draft": N, "active": M, "archived": K}
    active_products: list[tuple[CalcProduct, CalcProductCosts]],  # ya calculados con rounding
) -> DashboardStats
```

Métricas exactas (cada una testeada en unit):
- `active_materials` = `material_status_counts["active"]`; `incomplete_materials` = `material_status_counts["incomplete"]` (status derivado persistido por B8).
- `active_products` / `draft_products` = counts de productos **no eliminados** por status (`archived` NO va en la respuesta).
- `avg_product_cost` / `avg_final_price`: promedio Decimal sobre los `active_products` de `costs.product_total_cost` / `costs.final_sale_price` → `.quantize(Decimal("0.01"), ROUND_HALF_UP)`, serializado a **str**; 0 activos → `Decimal("0.00")` (paridad legacy `: 0`).
- `top_by_price`: **≤5** productos activos con mayor `final_sale_price` (desc); item `{id, name, final_sale_price (str), margin_percent}`.
- `bottom_by_margin`: **≤5** productos activos con menor `margin_percent` (asc); item `{id, name, product_total_cost (str), margin_percent}`.
- Ties → `name` asc (determinístico para tests). Menos de 5 productos → lista más corta.
- `DashboardStats`: frozen dataclass con los 8 campos exactos del response de la spec.
- El repo aporta los datos crudos (`dashboard_data(rounding_mode)`: counts por status + activos con líneas → costs vía `compute_costs`); el router orquesta repos + función pura (el material repo da `count_by_status()`).

## Endpoints (según `api_endpoints.md` §FASE CC, líneas ~189–192)
Todos bajo el `router` existente (`prefix="/calc"`). Montos/cantidades salen como **str** (Money de `api/v1/money.py`).

- `POST /calc/products/recalculate-all` — `require_admin` (write, D2). Sin body. → 200 `{"recalculated": N}` / 401 sin sesión / 403 no-admin.
- `GET /calc/products/price-list` — `get_current_user`. `?q,category_id?,page,page_size` → 200 `{items,total,page,page_size}` / 401. (Regla 3.)
- `GET /calc/products/price-list/export` — `get_current_user`. `?q,category_id?` → 200 `text/csv` / 401. (Regla 3.)
- `GET /calc/dashboard` — `get_current_user`. Sin params → 200 `{active_materials, active_products, draft_products, incomplete_materials, avg_product_cost, avg_final_price, top_by_price, bottom_by_margin}` / 401. (Regla 4.)
- `GET /calc/products` — **cambio**: `?q,category_id?,status?,sort?,dir?,page,page_size` (regla 2); códigos y filtros previos intactos.

## Patrones a seguir (ficheros de referencia reales)
- Domain frozen dataclass + función pura (ValueError donde aplique): `backend/src/domain/calc_product.py` (`compute_costs`, `apply_rounding`) y `calc_material.py`.
- Recalculate individual (extraer/reutilizar su lógica): `SQLCalcProductRepository.recalculate` en `backend/src/data/repositories/calc/sql_calc_product_repository.py` (~línea 445) + `_next_version_number`; `list` con accent_fold/filtros/paginación (~línea 177).
- Materiales (count por status, estilo del `list` existente): `backend/src/data/repositories/calc/sql_calc_material_repository.py`; ORM con `status` persistido: `CalcMaterialORM` en `backend/src/data/models.py` (~línea 159).
- Endpoints + helpers existentes: `backend/src/api/v1/calc/router.py` — `_settings_defaults` (~línea 1023), `recalculate_product` (~línea 1448), `list_products` (B9), responses/204/JSONResponse estilo B4–B9.
- Schemas Pydantic v2 `extra="forbid"` + `Literal` + str de montos: `backend/src/api/v1/calc/schemas.py`.
- Dependency injection (ya existen `get_calc_product_repository`, `get_calc_material_repository` — no crear nuevas): `backend/src/api/v1/calc/dependencies.py`.
- Tests de integración: `backend/tests/integration/api/test_calc_products_api.py` — copiá los fixtures (`db_session`/`client` con todos los overrides + `_token_for`/`_admin` + helpers `_create_material`/`_create_product`/`_set_settings`/`_create_product_category`) y agregá el override de `get_calc_material_repository` donde falte.
- CSV/Response con headers: `fastapi.responses.Response`/`Response(media_type="text/csv", headers={"Content-Disposition": ...})` (stdlib `csv`, sin nueva dependencia).
- `accent_fold`: `backend/src/data/accent.py`.

## Prohibiciones (safe mode)
1. **No tocar legacy**: nada bajo `api/v1/settings`, `api/v1/pricing`, `domain/pricing.py`, ingredients/stock. Coexistencia (L2).
2. **No tocar B1–B9** salvo lo documentado aquí: (a) cambio D5/RF-P3CC-01 del endpoint `GET /calc/products` (sort/dir + item) y (b) refactor local de `recalculate` → `_recalculate_one` (comportamiento IDENTICO, tests B9 sin tocar y verdes) y appends a `sql_calc_product_repository.py`, `sql_calc_material_repository.py`, `router.py`, `schemas.py`. Nada de reestructurar lo demás; `domain/calc_product.py` inmutable.
3. **Money como Decimal, serializado a str**: float prohibido en montos; `ROUND_HALF_UP`; el `cost` del CSV/price-list NUNCA se redondea (redondeo solo sobre `final_sale_price`, B9).
4. **Costs/snapshots nunca del cliente**: todo lo calculado sale del motor con `rounding_mode` de settings; ningún nuevo campo de payload (`extra="forbid"`).
5. **Auth D2**: GETs `get_current_user` (401), `recalculate-all` `require_admin` (403 no-admin).
6. **Route-order**: `price-list`/`price-list/export` registrados antes de `/products/{product_id}`.
7. No migraciones a mano (tests usan `Base.metadata.create_all`); no importar/ejecutar el JS legacy (la paridad de métricas se prueba con valores esperados); no agregar dependencias nuevas.
8. No commitear ni pushar.

## Criterio de salida (obligatorio)
Con 3 productos `active` (con categoría, 1 sin categoría), 1 `draft`, 1 `archived`, 1 eliminado, y un material cuyo precio cambia después de crear los productos:
- `POST /calc/products/recalculate-all` → `{"recalculated": 3}`: solo los activos cambian (líneas re-resueltas, `last_recalculated_at` set; versión creada solo en los cuyo final cambió, con `version_number` continuo); draft/archived/eliminado intactos.
- `GET /calc/products/price-list` → solo los 3 activos, con `category_name` correcta (null donde no hay) y `final_sale_price` = motor + redondeo del `rounding_mode` de settings.
- `GET /calc/products/price-list/export` → CSV con header exacto de la spec, 3 filas en orden por nombre, `cost` pre-redondeo.
- `GET /calc/dashboard` → counts exactos (2 incompletos si se siembran, etc.), promedios = promedio de los 3 activos cuantizado a centavos, `top_by_price`/`bottom_by_margin` con ≤5 items en el orden esperado.
- `GET /calc/products?sort=price&dir=desc` y `?sort=margin&dir=asc` → órdenes correctas contra valores calculados.

## Gate final (exacto)
```
cd backend
python -m pytest -q
```
→ **verde total, 0 regresiones**. Baseline actual (verificado 2026-10-27 sobre B9, commit `183d2ac`): `473 passed, 0 failed`. Al terminar debe ser ≥ 473 + tus tests nuevos, 0 failed. Además: `python -m pytest -q tests/unit/domain/test_calc_dashboard.py` verde y cobertura domain del nuevo módulo > 90%, y `python -m pytest -q tests/integration/api/test_calc_products_api.py` verde (tests B9 intactos).

## Output esperado
1. Resumen: archivos nuevos/modificados + count de tests nuevos + cómo quedó el sort (Python vs SQL) y el refactor `_recalculate_one`.
2. Resultado literal del gate `python -m pytest -q`.
3. Dudas/bloqueantes.

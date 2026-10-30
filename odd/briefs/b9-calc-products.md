# Brief B9 — Motor de precio + `calc_product` con líneas snapshot (backend)

Tarea: B9 de `odd/tasks/cost-calculator.md` (T-B9). Backend solo; la UI (F3/F4) son otras tareas.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea B9 + spec S5 + S3 (admin-only) + S8 (TDD).
- `docs/specs/p04_product_detail.md` §P4-CC → RF-P4CC-01..08 (campos, líneas snapshot, motor exacto, redondeo, recalculate, versiones, detalle).
- `docs/specs/api_endpoints.md` §FASE CC → tabla "CC Productos" (líneas ~179–188; rutas, payloads, códigos exactos).
- **Fuente legacy del motor (paridad obligatoria)**: `E:/toscana/calculadora-costos-toscana/src/lib/pricing.js` (78 líneas). `calcProductPricing` y `applyRounding` son la referencia numérica; NO se importa el código JS, se reimplementa con Decimal.
- Decisias del usuario (verbatim en `PREGUNTAS.md`, respetarlas):
  - **D4**: material `incomplete` (`unit_cost = None`) → snapshot en `0.00`, **sin error** (paridad legacy: el producto sigue calculable).
  - **D5**: listado `GET /calc/products` = `?q` (nombre Y SKU) + filtros + paginación, **orden fijo por nombre** — sin `?sort,?dir` (quedan para B10 si la spec lo exige ahí).
  - **D2**: auth patrón B3–B8: GETs con `get_current_user` (401 sin sesión), writes con `require_admin` (403 no-admin).

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`. La rama en la que trabajes DEBE contener B8: `git merge-base --is-ancestor d04cd5c HEAD` → exit 0 (B8 está en `feat/b8-calc-materials`, commit `d04cd5c`, PR #29; el worktree actual ya lo contiene). B9 se apila sobre B8, no sobre main.
- **NO commitear ni pushar** — el orquestador lo hace.
- Código/tests en inglés; docstrings en español (convención del repo). No agregar dependencias nuevas.

## TDD: RED primero
Escribí los tests de unit+integración en rojo antes del código. Cobertura domain `calc_product` > 90% (S8).

## Alcance (archivos)
| Archivo | Cambio |
|---|---|
| `backend/src/domain/calc_product.py` | NUEVO: motor de precio + `CalcProduct` + líneas + `CalcProductVersion` + `CalcProductCosts` (frozen dataclasses) + `apply_rounding()` |
| `backend/src/data/models.py` | APPEND: `CalcProductORM`, `CalcProductMaterialORM`, `CalcProductLaborORM`, `CalcProductExtraCostORM`, `CalcProductVersionORM` |
| `backend/src/data/repositories/calc/sql_calc_product_repository.py` | NUEVO: CRUD + líneas + snapshots + versions + recalculate |
| `backend/src/data/repositories/calc/sql_calc_material_repository.py` | SOLO: reemplazar `count_in_use` stub (TODO(B9), línea ~227) por consulta real |
| `backend/src/data/repositories/calc/sql_calc_product_category_repository.py` | SOLO: reemplazar `count_in_use` stub (TODO(B9), línea ~110) por consulta real |
| `backend/src/api/v1/calc/router.py` | APPEND: 8 endpoints nuevos (no tocar los existentes) |
| `backend/src/api/v1/calc/schemas.py` | APPEND: `ProductLineMaterialIn/Out`, `ProductLineLaborIn/Out`, `ProductLineExtraCostIn/Out`, `ProductCostsResponse`, `ProductCreate`, `ProductUpdate`, `ProductResponse`, `ProductDetailResponse`, `ProductListResponse`, `ProductVersionResponse`, `ProductVersionListResponse` |
| `backend/src/api/v1/calc/dependencies.py` | APPEND: `get_calc_product_repository` |
| `backend/tests/unit/domain/test_calc_product.py` | NUEVO |
| `backend/tests/integration/api/test_calc_products_api.py` | NUEVO |

## El motor (paridad exacta con `pricing.js`, todo Decimal `ROUND_HALF_UP`, NUNCA float)

Funciones puras en `domain/calc_product.py`, estilo `compute_unit_cost` de `domain/calc_material.py` (ValueError → 422 en API):

1. **Líneas** (faltar valor → 0, paridad `|| 0` del JS; valores negativos → ValueError):
   - `calc_material_line_cost(quantity_used, unit_cost)` = `quantity_used × unit_cost`
   - `calc_labor_line_cost(hourly_rate, minutes_required)` = `hourly_rate × (minutes_required / 60)`
   - `calc_extra_line_cost(unit_cost, quantity)` = `unit_cost × quantity`
   - Cada total se cuantiza a centavos: `.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
2. **`calc_product_pricing(materials_cost_total, labor_cost_total, extra_cost_total, margin_percent, discount_percent, tax_percent) -> CalcProductCosts`** (frozen dataclass con los 6 montos, SIEMPRE en centavos cuantizados, en este orden de cálculo — idéntico al JS línea a línea):
   - `cost_total = materials + labor + extra`
   - `price_before_discount = cost_total / (1 − margin/100)`; **guarda: si `margin_percent >= 100` → `price_before_discount = cost_total`** (evita división por cero; RF-P4CC-03)
   - `profit_amount = price_before_discount − cost_total`
   - `discount_amount = −(cost_total + profit_amount) × (discount/100)`
   - `adjusted_profit_amount = profit_amount + discount_amount`
   - `tax_amount = (cost_total + adjusted_profit_amount) × (tax/100)`
   - `final_sale_price (sin redondear) = cost_total + adjusted_profit_amount + tax_amount`
   - Percents fuera de [0, 100] → ValueError (422 en API).
3. **`apply_rounding(value, mode) -> Decimal`** — se aplica **SOLO a `final_sale_price`** (RF-P4CC-04), nunca a los otros 5 montos:
   - `none` → value sin tocar
   - `integer` → `(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)`
   - `multiple_10` → `(value / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 10`
   - `commercial_99` → `(value / 100).to_integral_value(rounding=ROUND_CEILING) * 100 − 1` (p. ej. 4937.77 → 4999; 500 → 499)
   - `rounding_mode` es el del singleton `calc_settings` (no existe por producto). Sin fila de settings → `none`. Modo desconocido → ValueError (422).
   - `rounding_mode` **nunca viene del cliente**: no está en ningún payload (`extra="forbid"` lo rechaza).

**Caso de paridad obligatorio en el test de unit** (valores elegidos para evitar ties de float del legacy; el resultado en centavos debe coincidir con `calcProductPricing` de `pricing.js`):
- Materiales: `2.5 × 456.80 = 1142.00` y `1 × 78.90 = 78.90`; Labor: `1500.00/h × 45 min = 1125.00`; Extra: `320.10 × 3 = 960.30` → `cost_total = 3227.30`
- `margin=30, discount=10, tax=19`:
  - `price_before_discount = 3227.30/0.70 = 4610.43` (cuantizado)
  - `profit_amount = 1383.13`, `discount_amount = −461.04`, `adjusted_profit_amount = 922.09`
  - `tax_amount = 4149.39 × 0.19 = 788.38`
  - `final_sale_price` con `rounding_mode = none` → **`4937.77`** (mismo valor que devuelve el JS)
  - Misma entrada con modos: `integer` → `4938`, `multiple_10` → `4940`, `commercial_99` → `4999`
- Además: margin `100` → `price_before_discount = cost_total`, `profit_amount = 0` (guarda sin excepción); margin `0` → `final = cost × (1+tax/100)` cuando no hay descuento.

## Modelo de datos esperado
`CalcProduct` (frozen dataclass, estilo `domain/calc_material.py`):
- `name: str` (1–120, strip, no-vacío), `sku: Optional[str]` (≤40, única entre productos no eliminados), `category_id: Optional[str]` (FK a product-categories), `description: Optional[str]` (≤500), `notes: Optional[str]` (≤500)
- `margin_percent: Decimal` (0–100), `discount_percent: Decimal` (0–100), `tax_percent: Decimal` (0–100) — **defaults del singleton `CalcSettings` cuando el payload no los envía** (RF-P5CC-01: 30/0/19)
- `status: str` ∈ `{draft, active, archived}`, default `draft` (allow-list; otro valor → ValueError → 422)
- `last_recalculated_at: Optional[datetime]` (set por recalculate)
- `deleted_at: Optional[datetime]` (soft delete)
- `id` uuid4, `created_at`, `updated_at` (UTC, defaults)

Líneas (frozen dataclasses, todas con `line_total_cost: Decimal` y `sort_order: int` = índice 0-based del payload; `id` uuid4):
- `CalcProductMaterialLine`: `material_id`, `material_name`, `quantity_used: Decimal` (Qty ≥ 0), `unit_of_measure_snapshot: Optional[str]`, `unit_cost_snapshot: Decimal`, `line_total_cost`, `sort_order`
- `CalcProductLaborLine`: `activity_name` (1–120), `hourly_rate: Decimal` (Money ≥ 0), `minutes_required: Decimal` (Qty ≥ 0), `line_total_cost`, `sort_order`
- `CalcProductExtraCostLine`: `concept_name` (1–120), `unit_cost: Decimal` (Money ≥ 0), `quantity: Decimal` (Qty ≥ 0), `line_total_cost`, `sort_order`

`CalcProductVersion` (append-only, estilo `CalcMaterialCostHistory`): `product_id`, `version_number: int`, los 6 montos (`product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price`, todos centavos), `changed_at`, `id`.

ORM (append en `data/models.py`, **mismo estilo que `CalcMaterialORM`**: `Column(...)`, montos/cantidades `String` — nunca float —, `DateTime(timezone=True)`):
- `CalcProductORM`: `__tablename__ = "calc_products"`; `id` PK String; `name` index; `sku` nullable index; `product_category_id = Column(String, ForeignKey("calc_product_categories.id"), nullable=True, index=True)`; `description`, `notes`; `margin_percent`/`discount_percent`/`tax_percent` `String, nullable=False`; `status` default `"draft"`; `deleted_at` `DateTime(timezone=True), nullable=True`; `last_recalculated_at` nullable; `created_at`/`updated_at` como en `CalcMaterialORM`.
- `CalcProductMaterialORM`: `__tablename__ = "calc_product_materials"`; `id` PK; `product_id` FK → `calc_products.id` nullable=False index; `material_id` FK → `calc_materials.id` nullable=False index; `material_name` nullable=False; `unit_of_measure_snapshot` nullable; `unit_cost_snapshot`/`quantity_used`/`line_total_cost` String nullable=False; `sort_order` Integer nullable=False.
- `CalcProductLaborORM`: `__tablename__ = "calc_product_labor"`; `id` PK; `product_id` FK index; `activity_name` nullable=False; `hourly_rate`/`minutes_required`/`line_total_cost` String nullable=False; `sort_order` Integer.
- `CalcProductExtraCostORM`: `__tablename__ = "calc_product_extra_costs"`; `id` PK; `product_id` FK index; `concept_name` nullable=False; `unit_cost`/`quantity`/`line_total_cost` String nullable=False; `sort_order` Integer.
- `CalcProductVersionORM`: `__tablename__ = "calc_product_versions"`; `id` PK uuid4; `product_id` FK → `calc_products.id` nullable=False index; `version_number` Integer nullable=False; los 6 montos `String, nullable=False`; `changed_at` DateTime nullable=False. **Append-only: solo INSERT.**

## Reglas de negocio (testeables en unit domain + integration)
1. **Snapshots resueltos SIEMPRE por el servidor al guardar** (RF-P4CC-02, security #8): para cada línea de material se resuelve desde `calc_materials` (vía `CalcMaterialORM` en la misma sesión): `material_name = material.name`, `unit_of_measure_snapshot = material.unit_of_measure`, `unit_cost_snapshot = material.unit_cost` **o `Decimal("0.00")` si es `None` (D4, sin error)**. `material_id` que no existe → 404 (patrón B8 de FK inválida). Los campos snapshot **nunca vienen del payload** (`extra="forbid"`).
2. **`line_total_cost` siempre derivado por el servidor** con el motor (regla 1 de "El motor"); nunca del cliente.
3. **`costs` (los 6 montos) siempre calculados por el servidor** en la lectura/escritura (RF-P4CC-05): se computan desde líneas + percents del producto + `rounding_mode` de settings. Nunca aceptados del payload (422).
4. **Reemplazo completo de líneas (transacción única)** (RF-P4CC-02): en POST y PATCH, las listas enviadas **reemplazan el set completo** (borrar viejas + insertar nuevas en el mismo commit). En PATCH: clave ausente → las líneas de ese tipo no cambian; clave `[]` → vacía el set de ese tipo.
5. **Versiones** (RF-P4CC-07, append-only): se crean **solo** en `POST /{id}/recalculate`, y **solo si el `final_sale_price` recalculado (redondeado) difiere del final calculado ANTES de re-resolver**. `version_number = max(version_number del producto) + 1` (primera versión = 1). POST/PATCH no generan versiones.
6. **Recalculate**: re-resuelve los snapshots de TODAS las líneas de material desde `calc_materials` actuales (D4 aplica), recalcula `line_total_cost` de cada una, `last_recalculated_at = now`, aplica regla 5; devuelve `{product, costs}` nuevos.
7. **SKU única** entre productos no eliminados, case/acento-insensitive (`accent_fold`, MISMO patrón de nombres únicos de B4–B7). Duplicado en POST/PATCH → **409 + `{"detail": "SKU ya en uso"}`** (`JSONResponse` estilo B4–B7). Si el dueño anterior fue eliminado (soft), el SKU vuelve a estar disponible.
8. **Soft delete**: `DELETE` setea `deleted_at` (nunca borra la fila ni las versiones). `GET /{id}` y el listado de productos eliminados → 404 / excluidos.
9. **`count_in_use` (completar los 2 stubs TODO(B9))**:
   - `SQLCalcMaterialRepository.count_in_use(material_id)`: `COUNT(DISTINCT product_id)` en `CalcProductMaterialORM` donde `material_id = :id` Y el producto **no eliminado** (join/filtro `CalcProductORM.deleted_at IS NULL`).
   - `SQLCalcProductCategoryRepository.count_in_use(category_id)`: `COUNT(*)` en `CalcProductORM` donde `product_category_id = :id` Y `deleted_at IS NULL`.

## Endpoints (según `api_endpoints.md` §FASE CC "CC Productos", líneas ~182–188)
Todos bajo el `router` existente (`prefix="/calc"`), `get_current_user` en GETs y `require_admin` en writes (D2 — patrón B3–B8 exacto). Montos/cantidades salen como **str** (Money/Qty de `api/v1/money.py`).

- `GET /calc/products` — `?q,category_id?,status?,page,page_size` (default 50, max `PAGINATION_MAX`=100) → 200 `{items,total,page,page_size}`. `?q` busca por **nombre Y SKU** con `accent_fold` (D5). `?status` ∈ `draft|active|archived`. **Orden fijo por nombre** (`func.lower(name)`, estilo B4–B8); sin `?sort,?dir`. Solo no-eliminados. Item = campos del producto (sin líneas ni costs).
- `POST /calc/products` — `{name*,sku?,category_id?,description?,notes?,margin_percent?,discount_percent?,tax_percent?,status?,materials:[{material_id*,quantity_used*}],labor:[{activity_name*,hourly_rate*,minutes_required*}],extra_costs:[{concept_name*,unit_cost*,quantity*}]}` → 201 `{product, costs}` / 404 (category_id o material_id inexistente) / 409 (SKU duplicada) / 422 (rangos, percents fuera de 0–100, negativos, status inválido, campos extra, montos del cliente). Body y líneas **`extra="forbid"`**; defaults de percents desde `CalcSettings` (repo `get` existente; sin fila → defaults 30/0/19 del dominio).
- `GET /calc/products/{id}` — `?include_versions?` → 200 `{product, materials, labor, extra_costs, costs, versions?}` / 404 (incluido si eliminado). `versions` solo presente con `include_versions=true` (listado completo, `version_number` desc).
- `PATCH /calc/products/{id}` — cualquier subconjunto de campos + `materials?/labor?/extra_costs?` (semántica regla 4) → 200 `{product, costs}` / 404 / 422 (sin campos → 422 "al menos un campo para actualizar", idéntico a B4–B7) / 404 FK inválida / 409 SKU.
- `DELETE /calc/products/{id}` → 204 / 404 (soft delete, regla 8).
- `POST /calc/products/{id}/recalculate` → 200 `{product, costs}` / 404 (regla 6).
- `GET /calc/products/{id}/versions` — `?page,page_size` → 200 `{items,total,page,page_size}`, items `{version_number, product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price, changed_at}` (montos str), **más recientes primero** (desc por `version_number`), 404 si el producto no existe.

Responses:
- `ProductResponse`: `id, name, sku, category_id, description, notes, margin_percent, discount_percent, tax_percent, status, last_recalculated_at, created_at, updated_at` (percents como número, estilo `CalcSettingsResponse`).
- `ProductCostsResponse`: los 6 campos str, nombre exacto del JS: `product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price`.
- Líneas en el detalle: como en "Modelo de datos" (montos str, `sort_order` int).

## Patrones a seguir (ficheros de referencia reales, B1–B8)
- Domain frozen dataclass + `__post_init__` con `ValueError` + funciones puras: `backend/src/domain/calc_material.py` (`compute_unit_cost`).
- ORM + mapeo `_to_domain`/`_to_orm` + repo async (list con `accent_fold` + count + offset/limit, get/create/update/delete, montos como `str`↔`Decimal`): `backend/src/data/repositories/calc/sql_calc_material_repository.py`.
- Endpoints CRUD (helpers `_x_response`, updates vía `model_dump(exclude_unset=True)`, `JSONResponse` para 409, `Response(204)`): `backend/src/api/v1/calc/router.py` (sección Materials, desde línea ~684).
- Schemas Pydantic v2 `extra="forbid"` + `field_validator` strip + Money/Qty: `backend/src/api/v1/calc/schemas.py`.
- Dependency injection del repo: `backend/src/api/v1/calc/dependencies.py`.
- Tests de integración (fixtures `db_session`/`client` con overrides de `get_db` + `get_user_repository` + repos calc, usuarios admin/customer sembrados, `_token_for`, registro SQL de `accent_fold`): `backend/tests/integration/api/test_calc_materials_api.py` (copiá el fixture y agregá el override de `get_calc_product_repository`).
- `accent_fold`: `backend/src/data/accent.py`.
- Settings para defaults + rounding_mode: `domain/calc_settings.py` (`CalcSettings` con los defaults 30/0/19 y `"none"`) + `sql_calc_settings_repository.py`.

## Prohibiciones (safe mode)
1. **No tocar legacy**: nada bajo `api/v1/settings`, `api/v1/pricing`, `domain/pricing.py`, `ingredients`/stock, ni el pricing preview. Coexistencia (L2).
2. **No tocar B1–B8** salvo: (a) los dos stubs `count_in_use` marcados `TODO(B9)` (es su único trabajo) y (b) appends a `router.py`/`schemas.py`/`dependencies.py`/`models.py`. Nada de reestructurar lo ya mergeado/apilado.
3. **Money como Decimal, serializado a str**: float prohibido en montos/cantidades; ORM los guarda como `String`. `ROUND_HALF_UP` en todo el motor (RNF-P4-03 / RNF-P5CC-01).
4. **Desglose y snapshots nunca del cliente** (security #8): `costs`, `line_total_cost`, campos `*_snapshot` → 422 si aparecen en el payload.
5. **Admin-only**: writes con `require_admin` (no-admin → 403); GETs con `get_current_user` (sin sesión → 401) — D2.
6. No migraciones a mano: tablas nuevas vía `Base.metadata.create_all` en tests (patrón existente); no scripts de migration.
7. No importar/ejecutar el JS legacy dentro de los tests; la paridad se prueba contra los valores esperados hardcodeados del caso de "El motor" (verificados contra `pricing.js`).
8. No agregar dependencias nuevas; no commitear ni pushar.

## Criterio de salida (obligatorio)
Con 2 materiales + 1 labor + 1 extra, `final_sale_price` del motor = el valor que devuelve `pricing.js` (`calcProductPricing` + `applyRounding`) — cubierto por el test de paridad de "El motor" (4937.77 / 4938 / 4940 / 4999 por modo de redondeo).

## Gate final (exacto)
```
cd backend
python -m pytest -q
```
→ **verde total, 0 regresiones**. Baseline actual (verificado 2026-10-27 sobre B8): `335 passed, 0 failed`. Al terminar debe ser ≥ 335 + tus tests nuevos, 0 failed. Además: `python -m pytest -q tests/unit/domain/test_calc_product.py` verde y cobertura domain del nuevo módulo > 90%.

## Output esperado
1. Resumen: archivos nuevos/modificados + count de tests nuevos.
2. Resultado literal del gate `python -m pytest -q`.
3. Dudas/bloqueantes.

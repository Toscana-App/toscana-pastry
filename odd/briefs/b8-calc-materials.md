# Brief B8 — `calc_material`: materiales de la calculadora (backend)

Tarea: B8 de `odd/tasks/cost-calculator.md` (T-B8). Backend solo; la UI (F2) es otra tarea.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea B8 + spec S4 + S3 (admin-only) + S8 (TDD).
- `docs/specs/p02_ingredients.md` §P2-CC → RF-P2CC-01..05 (campos, derivaciones, historial, búsqueda, delete).
- `docs/specs/api_endpoints.md` §FASE CC → tabla "CC Materiales" (rutas, payloads, códigos exactos).
- `docs/specs/p05_settings.md` §P5-CC → RF-P5CC-07 (búsqueda `?q` + paginación), RF-P5CC-08 (admin-only), RNF-P5CC-01/02 (Decimal + `ROUND_HALF_UP`, Pydantic `extra="forbid"`).
- Patrón de referencia: B1-B7 ya mergeados (PR #20, `bbd28a2`) — ver "Patrones a seguir".

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`. La rama en la que trabajes DEBE contener el merge de PR #20 (`git merge-base --is-ancestor bbd28a2 HEAD` → exit 0); el worktree actual ya lo contiene. No crear worktree.
- **NO commitear ni pushar** — el orquestador lo hace.
- Código/tests en inglés; docstrings en español (convención del repo). No agregar dependencias nuevas.

## TDD: RED primero
Escribí los tests de unit+integración en rojo antes del código. Cobertura domain `calc_material` > 90% (S8).

## Alcance (archivos)
| Archivo | Cambio |
|---|---|
| `backend/src/domain/calc_material.py` | NUEVO: `CalcMaterial` + `CalcMaterialCostHistory` (frozen dataclasses) + `compute_unit_cost()` + `derive_status()` |
| `backend/src/data/models.py` | APPEND: `CalcMaterialORM` + `CalcMaterialCostHistoryORM` |
| `backend/src/data/repositories/calc/sql_calc_material_repository.py` | NUEVO: CRUD + historial |
| `backend/src/data/repositories/calc/sql_calc_material_category_repository.py` | SOLO: reemplazar `count_in_use` stub (TODO(B8)) por consulta real a `CalcMaterialORM.material_category_id` |
| `backend/src/data/repositories/calc/sql_calc_supplier_repository.py` | SOLO: reemplazar `count_in_use` stub (TODO(B8)) por consulta real a `CalcMaterialORM.supplier_id` |
| `backend/src/api/v1/calc/router.py` | APPEND: 6 endpoints nuevos (no tocar los existentes) |
| `backend/src/api/v1/calc/schemas.py` | APPEND: `MaterialCreate`, `MaterialUpdate`, `MaterialResponse`, `MaterialListResponse`, `CostHistoryResponse`, `CostHistoryListResponse` |
| `backend/src/api/v1/calc/dependencies.py` | APPEND: `get_calc_material_repository` |
| `backend/tests/unit/domain/test_calc_material.py` | NUEVO |
| `backend/tests/integration/api/test_calc_materials_api.py` | NUEVO |

## Modelo de datos esperado
`CalcMaterial` (frozen dataclass, estilo `domain/calc_settings.py`):
- `name: str` (1–120, strip, no-vacío), `internal_code: Optional[str]` (≤40), `category_id: Optional[str]`, `supplier_id: Optional[str]`, `unit_of_measure: Optional[str]` (≤20), `purchase_total_price: Optional[Decimal]` (Money ≥ 0), `package_quantity: Optional[Decimal]` (Qty > 0 si presente), `notes: Optional[str]` (≤500)
- `unit_cost: Optional[Decimal]` y `status: str` — **derivados por el servidor en el repo/router, nunca parámetros de entrada del cliente** (RF-P2CC-02/03, security #8).
- `id` uuid4, `created_at`, `updated_at` (UTC, defaults) — igual que `CalcSupplier`.

`CalcMaterialORM` (append en `data/models.py`, **mismo estilo que `CalcSupplierORM`/`CalcDefaultCostORM`**: `Column(...)`, montos como `String` — nunca float —, `DateTime(timezone=True)`):
- `__tablename__ = "calc_materials"`; `id` PK String; `name` index; `internal_code`; `unit_of_measure`; `notes`
- `material_category_id = Column(String, ForeignKey("calc_material_categories.id"), nullable=True, index=True)`
- `supplier_id = Column(String, ForeignKey("calc_suppliers.id"), nullable=True, index=True)`
- `purchase_total_price` / `package_quantity` / `unit_cost`: `Column(String, nullable=True)` (None = "sin dato" → status `incomplete`)
- `status: String, nullable=False, default="incomplete"`

`CalcMaterialCostHistoryORM`:
- `__tablename__ = "calc_material_cost_history"`; `id` PK uuid4; `material_id` FK → `calc_materials.id`, nullable=False, index
- `previous_unit_cost` / `new_unit_cost`: `String, nullable=True`
- `changed_at: DateTime(timezone=True), nullable=False`. **Append-only: solo INSERT, nunca UPDATE/DELETE** (estilo `StockMovementORM`, RF-P2-04).

## Reglas de negocio (todas testeables en unit domain)
1. **`compute_unit_cost(purchase_total_price, package_quantity) -> Optional[Decimal]`**: si falta cualquiera → `None`; si `package_quantity == 0` → error (422 en API, `ValueError` en domain); si no: `(purchase / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. Float nunca toca montos (RNF-P5CC-01).
2. **`derive_status(purchase_total_price, package_quantity) -> str`**: falta precio O cantidad → `"incomplete"`; si no → `"active"`. (Ver Duda D1 sobre `inactive`.)
3. **Historial** (RF-P2CC-04): insertar UNA fila cuando el `unit_cost` computado DESPUÉS de la operación difiere del ANTES:
   - POST con precio y cantidad presentes → fila con `previous_unit_cost=None`, `new_unit_cost=<valor>` (alta inicial).
   - POST incomplete → **sin** fila.
   - PATCH con `new != old` (incluye `valor → None` al quitar precio/cantidad) → fila con ambos valores. PATCH sin cambio de `unit_cost` → **sin** fila.
   - La comparación es sobre el valor **computado** (re-roundeado), no sobre los strings crudos.
4. **FK**: `category_id`/`supplier_id` deben existir en sus tablas → si no, 404 (POST y PATCH; validar contra el repo correspondiente ya existente).
5. **Delete en uso** (S4): si el material está referenciado por líneas de productos → 409 + body `{"impacted_products": N}`. La tabla de líneas es de B9 (no existe aún): implementá el chequeo llamando a `repo.count_in_use(material_id)` y dejá ese método como **stub `return 0` con docstring `TODO(B9)`** — MISMO patrón que B4/B6 dejaron. El camino 409 se testa con monkeypatch del `count_in_use` devolviendo N.
   - **Delete con historial de costos**: el historial es append-only, así que un material con filas en `calc_material_cost_history` NO se puede borrar → 409 + body `{"detail": "has_cost_history"}` (se evalúa después del chequeo de uso en productos). Material sin historial → 204.

## Endpoints (según `api_endpoints.md` §FASE CC "CC Materiales")
Todos bajo el `router` existente (`prefix="/calc"`), con `get_current_user` en GET y `require_admin` en writes (patrón B3-B7 exacto — ver `router.py`).

- `GET /calc/materials` — `?q,category_id?,supplier_id?,status?,page,page_size` (page_size default 50, max `PAGINATION_MAX`=100) → 200 `{items,total,page,page_size}`. `?q` busca por **nombre Y `internal_code`**, case/acento-insensitive con `accent_fold` (RF-P2CC-05, mismo patrón que B4-B7). `?status` filtra por `active|incomplete`. Orden por nombre (estilo B7).
- `POST /calc/materials` — `{name*,internal_code?,category_id?,supplier_id?,unit_of_measure?,purchase_total_price?,package_quantity?,notes?}` → 201 `{material}` / 422 (rangos, `package_quantity` 0, campos extra o prohibidos) / 404 (FK inválida). Body **`extra="forbid"`**; `unit_cost` y `status` en el payload → 422.
- `GET /calc/materials/{id}` → 200 `{material}` / 404.
- `PATCH /calc/materials/{id}` — campos opcionales (mismos que POST) → 200 / 404 / 422 (sin campos → 422 "al menos un campo para actualizar", idéntico a B4-B7) / 404 FK inválida. Recalcula `unit_cost`/`status` sobre el resultado post-merge y aplica regla 3 de historial.
- `DELETE /calc/materials/{id}` → 204 / 404 / 409 `{"impacted_products":N}` (regla 5) / 409 `{"detail":"has_cost_history"}` (material con historial de costos).
- `GET /calc/materials/{id}/cost-history` — `?page,page_size` → 200 `{items,total,page,page_size}`, items `{previous_unit_cost, new_unit_cost, changed_at}` (montos como **string** vía Money), **más recientes primero** (desc por `changed_at`), 404 si el material no existe.

Responses: `unit_cost`/`purchase_total_price`/`package_quantity` salen como **str** en JSON (usar `Money`/`Qty` de `api/v1/money.py` — `PlainSerializer(when_used="json")`, igual que `DefaultCostResponse`). `MaterialResponse`: `id, name, internal_code, category_id, supplier_id, unit_of_measure, purchase_total_price, package_quantity, unit_cost, notes, status, created_at, updated_at`.

## Patrones a seguir (ficheros de referencia reales, B1-B7)
- Domain frozen dataclass + `__post_init__` con `ValueError`: `backend/src/domain/calc_settings.py` (`CalcSupplier`, `CalcDefaultCost`).
- ORM + mapeo `_to_domain`/`_to_orm` + repo async (list con `accent_fold` + count + offset/limit, get/create/update/delete): `backend/src/data/repositories/calc/sql_calc_default_cost_repository.py` y `sql_calc_supplier_repository.py`.
- Endpoints CRUD (helpers `_x_response`, updates vía `model_dump(exclude_unset=True)`, `JSONResponse` para 409, `Response(204)`): `backend/src/api/v1/calc/router.py` (secciones Suppliers / Default Costs).
- Schemas Pydantic v2 `extra="forbid"` + `field_validator` strip + Money/Qty: `backend/src/api/v1/calc/schemas.py`.
- Dependency injection del repo: `backend/src/api/v1/calc/dependencies.py`.
- Tests de integración (fixtures `db_session`/`client` con overrides de `get_db` + `get_user_repository` + repos calc, usuarios admin/customer sembrados, `_token_for`): `backend/tests/integration/api/test_calc_support_api.py` (copiá el fixture y agregá el override de `get_calc_material_repository`).
- `accent_fold`: `backend/src/data/accent.py` (ya registrada como función SQL en SQLite por las fixtures).

## Prohibiciones (safe mode)
1. **No tocar legacy**: nada bajo `api/v1/settings`, `api/v1/pricing`, `ingredients`/stock (P2 legacy), ni el pricing preview. Coexistencia (L2).
2. **No tocar B1-B7** salvo: (a) los dos stubs `count_in_use` marcados `TODO(B8)` (es su único trabajo) y (b) appends a `router.py`/`schemas.py`/`dependencies.py`/`models.py`. Nada de reestructurar lo mergeado.
3. **Money como Decimal, serializado a str**: float prohibido en montos/cantidades; ORM los guarda como `String`.
4. **`unit_cost` y `status` nunca del cliente**: `extra="forbid"` en Create/Update los rechaza con 422.
5. **Admin-only**: writes con `require_admin` (no-admin → 403; sin sesión → 401 en todo).
6. No migraciones manuales a mano: las tablas nuevas se crean vía `Base.metadata.create_all` en tests (patrón existente); no escribir scripts de migration.
7. No agregar dependencias nuevas; no commitear ni pushar.

## Gate final (exacto)
```
cd backend
python -m pytest -q
```
→ **verde total, 0 regresiones**. Baseline actual: `644 passed, 5 skipped`. Al terminar debe ser ≥ 644 + tus tests nuevos, mismo skipped, 0 failed. Además: `python -m pytest -q tests/unit/domain/test_calc_material.py` verde y cobertura domain del nuevo módulo > 90%.

## Output esperado
1. Resumen: archivos nuevos/modificados + count de tests nuevos.
2. Resultado literal del gate `python -m pytest -q`.
3. Dudas/bloqueantes.

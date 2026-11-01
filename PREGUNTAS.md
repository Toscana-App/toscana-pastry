# PREGUNTAS — orquestador autónomo

Log de dudas que el orquestador (sesión de pi) no puede resolver solo. El usuario las lee y define cómo seguir. Formato: fecha, tarea, pregunta, y **decisión propuesta** (lo que el orquestador va a hacer si no hay respuesta).

---

## [CERRADA por decisión] 2026-10-27 — B8 (cost-calculator): status de materiales — resuelta en d04cd5c (B8 DONE)

**Contexto**: §P2-CC menciona estados `active | inactive | incomplete` (la app de origen tenía toggle manual de `inactive`), pero la línea S4 del task doc dice "**status derivado**" y el payload de `api_endpoints.md` §FASE CC **no incluye `status`** en POST/PATCH de materiales.

**Pregunta**: ¿el status de `calc_material` debe ser 100% derivado (`incomplete` | `active`) sin setter del cliente, o se necesita el toggle manual `inactive`?

**Decisión propuesta (lo que voy a hacer)**: status 100% derivado, siguiendo el contrato más específico (payload publicado). Si se quiere el toggle manual, se actualiza S4 + endpoints antes de B8.

---

## [CERRADA por decisión] 2026-10-27 — B8 (cost-calculator): auth en GETs de /calc — resuelta en d04cd5c (B8 DONE, patrón B3-B7)

**Contexto**: S3 dice que todo `/api/v1/calc` exige rol admin, pero B3–B7 (mergeados y aprobados en PR #20) dejan los `GET` con `get_current_user` (solo 401) y `require_admin` solo en writes.

**Pregunta**: ¿B8 sigue el patrón mergeado (GET = 401 cualquier usuario autenticado; writes = 403 non-admin), o se exige 403 también en GETs según S3?

**Decisión propuesta (lo que voy a hacer)**: seguir el patrón mergeado de B3–B7 (no retroceder trabajo aprobado). Si se quiere 403 en GETs, es un fix separado de B3–B7.

---

## [ABIERTA] 2026-10-27 — PRs: merge en cascada

**Contexto**: hay PRs apilados abiertos: #27 (feat/c1-mercadopago-payments → main) y #28 (fix/english-code → #27). El loop autónomo va a seguir apilando PRs (B8 → main, B9 → B8, ...).

**Pregunta**: ¿debo hacer merge de PRs yo mismo cuando queden verdes (requiere permisos en el repo), o los dejo abiertos para que el usuario los revise/mergee en lote?

**Decisión propuesta (lo que voy a hacer)**: dejar PRs abiertos apilados; solo empujo commits nuevos a las ramas existentes. El usuario mergea cuando quiera.

---

## [CERRADA por decisión] 2026-10-27 — B9 (cost-calculator): snapshot de material `incomplete` — fijada en odd/briefs/b9-calc-products.md (D4: snapshot 0.00)

**Contexto**: el motor B9 guarda snapshots de material por línea (`material_name`, `unit_of_measure_snapshot`, `unit_cost_snapshot`). El spec (§FASE CC / RF-P4CC-03) no define qué pasa si el material referenciado es `incomplete` (unit_cost = None). El legacy JS permitía unit_cost 0 (cálculo en cero).

**Pregunta**: ¿rechazar la línea (422) o snapshot en `0.00`?

**Decisión propuesta (lo que voy a hacer)**: snapshot en `0.00` (sin error) — paridad con legacy, el producto sigue calculable y el material se puede completar después (recalculate re-resuelve el snapshot).

---

## [CERRADA por decisión] 2026-10-27 — B9 (cost-calculator): listado GET /calc/products — fijada en odd/briefs/b9-calc-products.md (D5: patrón B4-B8)

**Contexto**: la tabla de endpoints §FASE CC tiene `GET /calc/products` con `?q,category_id?,status?,page,page_size`. El task doc B9 dice "API CRUD" sin detalle de sort.

**Pregunta**: ¿el listado B9 incluye ordenamiento (`?sort,?dir`)?

**Decisión propuesta (lo que voy a hacer)**: listado con `?q` (nombre y SKU, accent-insensitive) + filtros + paginación, orden fijo por nombre — MISMO patrón B4-B8. Sort avanzado queda para B10 (dashboard/price-list) si la spec lo exige ahí.

> **CERRADA (consecuencia, 2026-10-27)**: la spec sí exige sort ahí (RF-P3CC-01 + `api_endpoints.md` §FASE CC `?sort ∈ {name,cost,price,margin}, ?dir`). B10 lo implementa en `GET /calc/products` (fijado en `odd/briefs/b10-recalculate-pricelist-dashboard.md`).

---

## [ABIERTA] 2026-10-27 — B10 (cost-calculator): acciones duplicar/archivar sin endpoint (RF-P3CC-02)

**Contexto**: RF-P3CC-02 menciona acciones por producto — **duplicar** (nuevo `draft` con líneas copiadas) y **archivar** (status → `archived`) — pero la tabla publicada de `api_endpoints.md` §FASE CC **no define endpoint** para ninguna (ni `POST /{id}/duplicate`, ni endpoint de archivo). Archivar ya es posible hoy vía `PATCH /calc/products/{id}` `{status:"archived"}` (B9).

**Pregunta**: ¿se necesita un endpoint `POST /calc/products/{id}/duplicate` (o similar) para B10/F4, o se queda fuera de alcance v1?

**Decisión propuesta (lo que voy a hacer)**: fuera de alcance de B10. Archivar = `PATCH` existente (ya funciona). Duplicar no se expone como endpoint; si F4 lo necesita, la UI puede copiar líneas vía `POST /calc/products` (o pedimos el endpoint entonces).

---

## [ABIERTA] 2026-10-27 — B10 (cost-calculator): item del listado `GET /calc/products` (B9 mínimo vs RF-P3CC-01)

**Contexto**: B9 shippeó el item del listado sin `category_name`/`product_total_cost`/`final_sale_price` (item mínimo por D5). RF-P3CC-01 los incluye explícitamente en el item. `calc_product` no persiste costos (son derivados por el motor, B9).

**Pregunta**: ¿B10 enriquece el item con `category_name, product_total_cost, final_sale_price` (costos calculados on-the-fly para cada fila de la página) aunque sea cambio en la respuesta de un endpoint ya mergeado (B9)?

**Decisión propuesta (lo que voy a hacer)**: sí, enriquecer según RF-P3CC-01 (B10 ya calcula costos por fila para el sort `cost`/`price`; no hay consumidores frontend aún — F4 no existe — así que no rompe nada). Fijado en `odd/briefs/b10-recalculate-pricelist-dashboard.md`.

---

## [ABIERTA] 2026-10-27 — B10 (cost-calculator): métricas dashboard y CSV — detalles no especificados

**Contexto**: RF-P3CC-05 da los nombres de los 8 campos pero no la semántica de promedios/ties, y §FASE CC da las columnas CSV sin formato exacto. `calc_product` no persiste costos → todo se calcula on-the-fly con `compute_costs` + `rounding_mode` del settings singleton (la única implementación posible; paridad de semántica con `Dashboard.jsx`/`PriceList.jsx` del legacy, sin importar código).

**Pregunta**: ¿confirmar estas decisiones de detalle?

**Decisión propuesta (lo que voy a hacer)** (fijadas en `odd/briefs/b10-recalculate-pricelist-dashboard.md`):
- `avg_product_cost`/`avg_final_price`: promedio Decimal sobre productos **activos no eliminados**, cuantizado `ROUND_HALF_UP` a centavos, str; 0 activos → `"0.00"` (paridad legacy).
- `top_by_price[≤5]` / `bottom_by_margin[≤5]`: solo activos; top por `final_sale_price` desc, bottom por `margin_percent` asc; **ties → nombre asc** (determinismo de tests); < 5 productos → lista más corta.
- `active_materials`/`incomplete_materials`: conteo por `calc_materials.status` (derivado persistido por B8); `archived` products no aparece en la respuesta.
- CSV: header exacto de la spec (`id,name,category,cost,margin_pct,final_price`, distinto de los headers en español del legacy), `cost` = `product_total_cost` **pre-redondeo** (el costo nunca se redondea), `category` = nombre de la categoría (vacío si no tiene), sin paginación, `filename="lista_precios.csv"` (paridad legacy), módulo stdlib `csv`.
- recalculate-all: MISMAS reglas que el recalculate individual B9 (versión solo si el final redondeado cambió; `last_recalculated_at` siempre set) + transacción única (1 commit).

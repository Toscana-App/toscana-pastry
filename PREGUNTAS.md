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

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

---

## [ABIERTA] 2026-10-28 — F1 (cost-calculator): stack de tests del frontend no existe

**Contexto**: S8 exige "Vitest para la UI", pero `frontend/package.json` **no tiene ningún runner de tests** (ni vitest, ni jest, ni cypress/playwright), ni config, ni un solo test en `frontend/src`. F1 es la primera tarea frontend del feature.

**Pregunta**: ¿confirmar el stack de tests para F1?

**Decisión propuesta (lo que voy a hacer, fijado en `odd/briefs/f1-calc-config.md`)**:
- devDependencies **de test, únicas nuevas**: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`; script `"test": "vitest run"`. Nada de UI libraries nuevas ni react-query/swr (los fetches son directos con `apiFetch`, como el resto del app).
- `frontend/vitest.config.ts`: `environment: "jsdom"`, alias `@` → `./src` (paridad con `tsconfig.json`), setup con `@testing-library/jest-dom/vitest`.
- Tests de componentes por tab (≥15), mockeando el **service** (`vi.mock("@/services/calcSettingsService")`), sin backend real. E2E fuera de alcance de F1.

---

## [ABIERTA] 2026-10-28 — F1 (cost-calculator): paginación y búsqueda en la UI de los ABM

**Contexto**: el backend lista con `?q` (1–120 chars) + `?page&page_size` (default 50, max 100, RF-P5CC-07), pero la spec de UI (§P5-CC "UI") solo dice "lista de cards en cada ABM con acciones inline" y no define controles de paginación ni comportamiento del search (debounce vs botón).

**Pregunta**: ¿confirmar la UI de listado para los 4 ABM?

**Decisión propuesta (lo que voy a hacer, fijado en `odd/briefs/f1-calc-config.md`)**:
- Cada ABM: `Input` de búsqueda que manda `?q` (debounce ~300 ms; `q` vacío → lista completa) + paginación prev/next con "total N" y `page_size=50` fijo (escala admin; sin selector de page_size).
- `EmptyState` cuando `items` está vacío; error de carga → toast danger + reintento (patrón `app/admin/page.tsx`).
- El fetch de cada tab es **lazy al activarse por primera vez** (RNF-P5CC-03: "1 GET por pestaña"): 0 requests al montar la página.

---

## [ABIERTA] 2026-10-29 — F2 (cost-calculator): UI de la página de materiales — ruta, form de edición y presentación del historial

**Contexto**: S7 dice "páginas de materiales, biblioteca de productos, editor de producto, price list, dashboard" pero no da la URL ni el detalle UI del page (a diferencia de §P5-CC, §P2-CC no tiene sección "UI"). La spec define solo la API (RF-P2CC-01..05). `MaterialResponse` trae `category_id`/`supplier_id` **sin nombres** (schemas.py:309), y el historial (RF-P2CC-04) solo está definido como endpoint paginado.

**Pregunta**: ¿confirmar estas decisiones de UI para F2?

**Decisión propuesta (lo que voy a hacer, fijado en `odd/briefs/f2-calc-materials.md`)**:
- Ruta: `/admin/calculadora/materiales` (hermano de `/admin/calculadora/configuracion`), `ProtectedRoute requiredRole="admin"`.
- Alta en card encima de la tabla (patrón F1 `CategoryAbm`); **edición en `Dialog`** con el mismo form (8 campos no caben en la fila de la tabla como en F1, que tenía 2 campos).
- Filtros `?category_id`/`?supplier_id`/`?status`: las opciones se cargan una sola vez al montar vía los endpoints F1 (`GET /calc/material-categories`, `GET /calc/suppliers`, `page_size=100`) y el mismo id→name map alimenta las columnas Categoría/Proveedor de la tabla (id sin match → "—"). Estado: solo `active|incomplete` (D1 de B8 cerrada: no existe `inactive`).
- Historial: botón "Historial" por fila → `Dialog` con tabla desc (más recientes primero, como el endpoint): columnas "Anterior" → "Nuevo" + fecha `es-AR`, paginado prev/next; vacío → "Sin cambios de costo registrados.".
- `unit_cost`/montos se muestran tal cual el `str` del servidor (sin formateo ni aritmética client-side); `incomplete` como chip read-only (`surface-soft` `#f4f4f4`).
- Página con `maxW="container.xl"` (la tabla tiene ~10 columnas; F1 usó `container.md` porque era forms/categorías).

---

## [ABIERTA] 2026-10-30 — F3 (cost-calculator): rutas del editor y navegación (F3-Q1)

**Contexto**: S7 dice "editor de producto" pero no da URLs; la biblioteca/lista (`GET /calc/products`) es F4 y aún no existe, así que F3 no tiene una página destino para "Volver". El legacy usaba `/products/new?id=...` (query params) + `/products/{id}` (detalle read-only separado).

**Pregunta**: ¿confirmar rutas y navegación de F3?

**Decisión propuesta (lo que voy a hacer, fijado en `odd/briefs/f3-calc-product-editor.md`)**:
- Rutas: `/admin/calculadora/productos/nuevo` (alta) y `/admin/calculadora/productos/[id]` (edición + detalle: versiones + recalcular + eliminar; el editor precargado IS el detalle — un solo componente `ProductEditor mode="create|edit"`, no dos páginas como el legacy).
- Tras POST 201 → `router.replace("/admin/calculadora/productos/{id}")` (el producto recién creado, que se recarga desde el servidor). Botón "Volver" y post-delete → `router.back()`. La lista index `/admin/calculadora/productos` la crea F4 (F3 no la crea; `nuevo`/`[id]` no colisionan con ella).

---

## [ABIERTA] 2026-10-30 — F3 (cost-calculator): summary en vivo — ¿preview client-side o solo del servidor? (F3-Q2)

**Contexto**: el título de F3 pide "summary en vivo", pero RF-P4CC-05 dice que los montos derivados son **solo-escritura del servidor** (security #8; `extra="forbid"` → 422 si el cliente los manda), y el endpoint que devuelve `costs` solo existe después de guardar/recalcular. El legacy sí calculaba el resumen en el browser (`calcProductPricing` de `pricing.js`, float) y reaccionaba al instante (RNF-P4-01 < 50 ms en el spec P4 legacy).

**Pregunta**: ¿el summary en vivo es un preview calculado en el cliente, o se muestran solo los costos del servidor (tras guardar/recalcular)?

**Decisión propuesta (lo que voy a hacer, fijado en el brief)**: **preview client-side** con un espillo puro del motor (`frontend/src/lib/calcPricing.ts`, JS number redondeado a centavos) — NUNCA enviado al servidor (los payloads siguen siendo solo `material_id/quantity` etc.; RF-P4CC-05 se mantiene intacto). El panel lleva el label fijo **"Preview — se confirma al guardar"** para distinguir el preview float de los valores Decimal autoritativos (puede diferir un centavo en ties). Los str del servidor (versiones, costos post-recalculate) se muestran tal cual.

---

## [ABIERTA] 2026-10-30 — F3 (cost-calculator): panel de simulación (F3-Q3)

**Contexto**: el spec §P4-CC no menciona "simulación"; pero el título de F3 la pide y la app de origen tiene `SimulationPanel.jsx` (botón "Simular": 3 percents de escenario + precio simulado + diferencia vs. actual, sin mutar el producto). L1: mantener la funcionalidad.

**Pregunta**: ¿se incluye la simulación en F3?

**Decisión propuesta (lo que voy a hacer, fijado en el brief)**: sí, paridad con el origen: botón "Simular" en el header → panel debajo del summary con 3 inputs de percent (estado propio, inicializados con los del form; cerrarlo NO muta el form), precio simulado (mismo espillo + rounding de settings) y "Diferencia vs. actual" (+verde/−rojo).

---

## [ABIERTA] 2026-10-30 — F3 (cost-calculator): select de materiales en las líneas (F3-Q4)

**Contexto**: el editor necesita elegir materiales existentes (`GET /calc/materials` es paginado, `page_size` máx 100; el catálogo puede excederlo). El legacy usaba un list local de 500. Chakra v3 trae `Combobox` (búsqueda + dropdown).

**Pregunta**: ¿cómo se busca/seleciona el material en cada fila?

**Decisión propuesta (lo que voy a hacer, fijado en el brief)**: `Combobox` por fila con búsqueda **asíncrona debounced 300 ms** contra `calcMaterialsService.listMaterials({q, page_size: 50})` (el service F2 existente, sin modificar); opción = nombre + `— unit cost {str}` (o "— incompleto"). Sin cargar todo el catálogo; sin "cargar más".

---

## [ABIERTA] 2026-10-30 — F3 (cost-calculator): semántica de save y CTA de status (F3-Q5)

**Contexto**: `ProductUpdate` soporta tres semánticas de líneas (ausente → no cambia; `[]` → vacía; lista → reemplazo completo) y el spec RF-P4CC-02 dice "el guardado reemplaza el set completo de líneas (transacción única)". El legacy tenía 2 CTA ("Borrador"/"Guardar" activo) y duplicar; el enunciado de la tarea pone `status` como campo del form.

**Pregunta**: ¿confirmar semántica de save y CTA?

**Decisión propuesta (lo que voy a hacer, fijado en el brief)**:
- El editor **siempre envía las 3 listas de líneas completas** en POST y PATCH (reemplazo, RF-P4CC-02 — la semántica "ausente no cambia" queda disponible para consumidores futuros, no para el editor).
- **Un solo CTA "Guardar"** + campo `status` en el form (Select draft/active/archived; default `draft` en alta, valor actual en edición) — cubre borrador/activo/archivar sin 3 botones (archivar desde el editor = cambiar status a archived).
- **Duplicar queda fuera de F3** (no hay endpoint de duplicate — decisión B10 en este mismo archivo; la lista F4 podrá ofrecerlo vía POST si se decide).

# Brief F3 — Editor de producto de la calculadora (`/admin/calculadora/productos/nuevo` + `/[id]`): líneas, summary en vivo, simulación, versiones, recalcular

Tarea: F3 de `odd/tasks/cost-calculator.md` (T-F3). **Frontend solo** (`frontend/`); el backend (B1–B10, 528 tests) está completo y NO se toca. 2 páginas nuevas (alta + edición/detalle) que comparten un editor: form del producto + 3 tablas de líneas editables + summary de costos en vivo + panel de simulación + histórico de versiones + recalcular + eliminar.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea F3 (aceptación completa) + specs S5 (`docs/specs/p04_product_detail.md` §P4-CC, motor de precio y líneas snapshot) y S7 (UI admin Next.js + Chakra v3 + `.claude/design/DESIGN.md`).
- `docs/specs/p04_product_detail.md` §P4-CC → RF-P4CC-01 (campos del producto y rangos), RF-P4CC-02 (3 tipos de línea con snapshot; el guardado **reemplaza el set completo** de líneas), RF-P4CC-03/04 (fórmula exacta del motor y modos de redondeo — la UI no la reimplementa para persistir, solo para preview), RF-P4CC-05 (`line_total_cost`, `*_snapshot` y los 6 montos son **solo-escritura del servidor**; `extra="forbid"` → 422 si el cliente los manda), RF-P4CC-06 (`POST /{id}/recalculate` devuelve el desglose), RF-P4CC-07 (versiones append-only paginadas), RF-P4CC-08 (detalle con líneas + desglose + `?include_versions`).
- API: verificada en `backend/src/api/v1/calc/router.py` (commit `79245d6`, PR #31) + `schemas.py` — ver sección "Endpoints" abajo con líneas exactas. Montos/cantidades viajan como **str** (`api/v1/money.py`); percents como **número**.
- Paridad con la app de origen (L1: mantener funcionalidad, sin importar código): `E:/toscana/calculadora-costos-toscana/src/pages/ProductEditor.jsx` (layout grid `[1fr,320px]`, cards, líneas inline, CTA), `src/components/products/ProductSummaryPanel.jsx` (resumen con 6 montos, precio final destacado), `src/components/products/SimulationPanel.jsx` (modo simulación: 3 percents + precio simulado + diferencia vs. actual), `src/pages/ProductDetail.jsx` (tablas de líneas read-only + historial de versiones).
- Tokens de diseño: `C:\Users\Usuario\toscana-pastry\.claude\design\DESIGN.md` — botones pill (`rounded="full"`), cards outline 1px `{colors.hairline-light}` sin shadow, danger `#e23b4a`, `surface-soft` `#f4f4f4`, success `#428619`.
- Decisias F3 pendientes (UI): `PREGUNTAS.md` → entradas **F3-Q1..Q5** con decisión propuesta a respetar.

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`, rama `feat/f3-calc-product-editor` (ya creada y apilada sobre F2: verificar `git merge-base --is-ancestor 4a6b80a HEAD` → exit 0, `4a6b80a` = PR #33). **NO commitear ni pushar** — el orquestador lo hace.
- Código en inglés; comentarios/docstrings en español (convención del repo).
- Stack de tests ya existe por F1 (Vitest + jsdom + Testing Library): NO tocar `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx` ni `package.json` (no se agregan dependencias).

## TDD: Vitest
Tests de componentes con `vitest` + `@testing-library/react` mockeando los **services** (`vi.mock("@/services/calcProductsService")`, `vi.mock("@/services/calcMaterialsService")`, `vi.mock("@/services/calcSettingsService")`) y el toaster (`vi.mock("@/lib/toaster")`), sin backend real — mismo patrón que `frontend/src/components/calc/MaterialsAbm.test.tsx` (vi.mock + fixtures + `renderWithProviders`). Render siempre con `renderWithProviders` de `frontend/src/test-utils.tsx`. Baseline: **46 tests verdes (9 archivos, F1 19 + F2 27)** que no pueden romperse.

## Alcance (archivos)
Todo bajo `frontend/`. Nada de `backend/`.

| Archivo | Cambio |
|---|---|
| `frontend/src/types/calc.ts` | EXTENDER (append, no reescribir lo existente): `ProductStatus = "draft" \| "active" \| "archived"`; `CalcProduct` (shape de `ProductResponse`: montos-percents como `number`, `sku/category_id/description/notes/last_recalculated_at` opcionales `string \| null`); `ProductCosts` (los 6 montos, `string`); `ProductLineMaterial`/`ProductLineLabor`/`ProductLineExtraCost` (shapes `Out`: montos/cantidades `string`, `sort_order: number`); `ProductLines`; `ProductWithLinesResponse {product, product_lines, costs}`; `ProductDetailResponse` (idéntico + `versions?: ProductVersion[]`); `ProductVersion` (shape de `ProductVersionResponse`); `ProductVersionListResponse`; `ProductLineMaterialInput {material_id, quantity_used: number}`; `ProductLineLaborInput {activity_name, hourly_rate: number, minutes_required: number}`; `ProductLineExtraCostInput {concept_name, unit_cost: number, quantity: number}`; `ProductCreatePayload` (campos de `ProductCreate`: percents `number`, status, 3 listas de inputs); `ProductUpdatePayload` (mismos, todos opcionales). Reutilizar `Material` existente para el select de materiales. |
| `frontend/src/services/calcProductsService.ts` | NUEVO: `calcProductsService` con 6 métodos (ver Endpoints). Reutilizar el patrón de `calcMaterialsService.ts` (helpers privados `buildQuery`/`jsonOptions`/`deleteViaApiFetch` — copiarlos locales a este archivo; NO modificar `calcMaterialsService.ts` ni `calcSettingsService.ts`). DELETE: 204 body vacío → `apiFetch` lanza `SyntaxError` → tragar como éxito (mismo truco que `calcMaterialsService.ts:36-44`). |
| `frontend/src/lib/calcPricing.ts` | NUEVO: **espillo del motor, preview-only** (ver "Summary en vivo"). Funciones puras exportadas: `computeLineTotals(materials, labor, extra)` y `computePricingPreview(materialsCost, laborCost, extraCost, marginPct, discountPct, taxPct, roundingMode)` → `{product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price}` (números, redondeados a centavos con `Math.round(x*100)/100`). Documentar en el header del archivo: preview aproximado en float — los valores persistidos los calcula el servidor con Decimal (RF-P4CC-05); NO mandar nunca estos números en payloads. |
| `frontend/src/app/admin/calculadora/productos/nuevo/page.tsx` | NUEVO: `"use client"`, `ProtectedRoute requiredRole="admin"`, `Container py={10} maxW="container.xl"`, `Heading` "Nuevo producto", renderiza `<ProductEditor mode="create" />`. Patrón de page: `frontend/src/app/admin/calculadora/materiales/page.tsx`. |
| `frontend/src/app/admin/calculadora/productos/[id]/page.tsx` | NUEVO: idem, recibe `params` (Next.js 15: `params` es `Promise` — verificar el pattern de params en la versión instalada), `Heading` "Editar producto", renderiza `<ProductEditor mode="edit" productId={id} />`. |
| `frontend/src/components/calc/ProductEditor.tsx` | NUEVO: contenedor del editor (ambos modos). Estado: form (name, sku, categoryId, description, notes, 3 percents, status), 3 listas de líneas, busy. Carga en modo edición (`getProduct(id, {includeVersions: true})`), opciones de categoría (una vez), defaults de percents (solo alta). Layout: grid `[1fr, 320px]` (responsive: 1 columna en mobile) — columna principal (card form + 3 cards de líneas) y sidebar sticky (summary + simulación). CTA: Volver, Simular (toggle), Recalcular (solo edición), Eliminar (solo edición), Guardar. Lógica de save/recalculate/delete (ver "Guardar / recalcular / eliminar"). |
| `frontend/src/components/calc/ProductMaterialLines.tsx` | NUEVO: tabla de líneas de materiales (ver "Tablas de líneas" — Combobox asíncrono + cantidad + total preview + quitar fila). Props: `items`, `onChange(items)`. |
| `frontend/src/components/calc/ProductLaborLines.tsx` | NUEVO: tabla de líneas de labor (nombre/tarifa/minutos + total + quitar). |
| `frontend/src/components/calc/ProductExtraLines.tsx` | NUEVO: tabla de líneas de costo extra (concepto/costo unitario/cantidad + total + quitar). |
| `frontend/src/components/calc/ProductSummaryPanel.tsx` | NUEVO: card sticky del resumen (subtotales por tipo + los 6 montos, precio final destacado `tabular-nums`, label "Preview — se confirma al guardar"; `discount_amount` negativo en rojo). Props: preview + subtotales. |
| `frontend/src/components/calc/SimulationPanel.tsx` | NUEVO: panel de simulación (paridad `SimulationPanel.jsx` del origen: 3 inputs de percent inicializados con los del form, precio simulado + "Diferencia vs. actual", botón cerrar; NO muta el form del editor). Props: subtotales, percents base, simBasePrice. |
| `frontend/src/components/calc/ProductVersionsCard.tsx` | NUEVO: card "Historial de versiones" (solo modo edición): filas desc `v{n} · fecha es-AR · cost · precio` desde las versiones cargadas (`include_versions=true` trae la lista completa desc; si el implementador prefiere el endpoint paginado, `listVersions` del service); vacío → "Sin historial de versiones.". Props: `versions`. |
| Tests (NUEVOS, 1 por componente + pages): `ProductEditor.test.tsx`, `ProductMaterialLines.test.tsx`, `ProductLaborLines.test.tsx`, `ProductExtraLines.test.tsx`, `ProductSummaryPanel.test.tsx`, `SimulationPanel.test.tsx`, `ProductVersionsCard.test.tsx`, `app/admin/calculadora/productos/nuevo/page.test.tsx`, `app/admin/calculadora/productos/[id]/page.test.tsx` | Vitest (ver "Cobertura de tests"). |

No se toca: `src/services/calcSettingsService.ts`, `src/services/calcMaterialsService.ts` (se **usa**, no se modifica), los 9 componentes F1/F2 de `src/components/calc/`, `configuracion/*`, `materiales/*`, `src/lib/api.ts`, `src/lib/toaster.tsx`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`, `src/types/calc.ts` más allá del append, `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx`, `package.json`, `next.config.ts`, `eslint.config.mjs`, `tsconfig.json`.

## Endpoints a consumir (verificados en `backend/src/api/v1/calc/router.py` + `schemas.py`)
Base: `apiFetch` ya prefija `NEXT_PUBLIC_API_URL || http://localhost:8000/api/v1` (`frontend/src/lib/api.ts:10`). Todos los GET piden sesión (401); los writes son admin-only (403 no-admin). `apiFetch` lanza `Error` con `error.detail` cuando hay (api.ts:71) — el toast muestra ese mensaje.

`ProductWithLinesResponse` (schemas.py:559): `{product: ProductResponse, product_lines: ProductLinesOut, costs: ProductCostsResponse}`.
- `ProductResponse` (schemas.py:473): `{id, name, sku?, category_id?, description?, notes?, margin_percent: number, discount_percent: number, tax_percent: number, status, last_recalculated_at?, created_at, updated_at}`.
- `ProductLinesOut` (schemas.py:553): `{materials: [{material_id, material_name, quantity_used: str, unit_of_measure_snapshot?: str, unit_cost_snapshot: str, line_total_cost: str, sort_order}], labor: [{activity_name, hourly_rate: str, minutes_required: str, line_total_cost: str, sort_order}], extra_costs: [{concept_name, unit_cost: str, quantity: str, line_total_cost: str, sort_order}]}`.
- `ProductCostsResponse` (schemas.py:515): `{product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price}` — **los 6 montos, todos str**.

- `POST /calc/products` (router.py:1181) — body `ProductCreate` (schemas.py:401, `extra="forbid"`): `{name* (1–120, sin solo-blancos), sku? (≤40; vacía/blank → null, única case/acento-insensitive), category_id?, description? (≤500), notes? (≤500), margin_percent? (0–100), discount_percent? (0–100), tax_percent? (0–100), status? ∈ {draft,active,archived} default "draft", materials: [{material_id*, quantity_used ≥ 0}], labor: [{activity_name* (1–120), hourly_rate ≥ 0, minutes_required ≥ 0}], extra_costs: [{concept_name* (1–120), unit_cost ≥ 0, quantity ≥ 0}]}` → **201** `ProductWithLinesResponse` / **404** material o categoría inexistente / **409** SKU duplicada (`detail: "SKU ya en uso"`) / **422** rangos, name vacío, o cualquier campo extra (`line_total_cost`, `*_snapshot`, `costs` — **nunca mandarlos**). Percents omitidos → defaults del settings singleton. Material `incomplete` → snapshot `0.00` **sin error** (D4 de B9).
- `GET /calc/products/{id}?include_versions=false` (router.py:1418) → **200** body `{product, materials[], labor[], extra_costs[], costs, versions?}` — **ojo: este endpoint no tiene `response_model` (dict)**: `materials/labor/extra_costs` son las listas planas (mismos shapes que `product_lines`), `costs` los 6 str, y `versions` (solo con `include_versions=true`) = lista completa **desc** `[{version_number, product_total_cost, profit_amount, discount_amount, adjusted_profit_amount, tax_amount, final_sale_price, changed_at}]` (sin paginación). 404 si no existe.
- `PATCH /calc/products/{id}` (router.py:1508) — body `ProductUpdate` (schemas.py:437, `extra="forbid"`): mismos campos que Create, **todos opcionales** (body vacío → 422). Semántica de líneas: **clave ausente → no cambia; `[]` → vacía ese set; lista → reemplazo completo** (transacción única). SKU: `409` si se toca y está en uso. → **200** `ProductWithLinesResponse` / 404 / 422.
- `DELETE /calc/products/{id}` (router.py:1662) → **204** / 404. Soft delete (versiones preservadas).
- `POST /calc/products/{id}/recalculate` (router.py:1682) → **200** `ProductWithLinesResponse` (re-resuelve los snapshots desde `calc_materials`, recalcula totales; crea versión solo si el `final_sale_price` redondeado cambió) / 404 / 422.
- `GET /calc/products/{id}/versions?page=1,page_size=50` (router.py:1718) → `ProductVersionListResponse` (schemas.py:642): `{items: [shape de versión], total, page, page_size}`, **más recientes primero** / 404. (Opcional si se usa `include_versions` del detalle.)
- (F1, existentes — para opciones/defaults, vía `calcSettingsService`): `getSettings()` (calcSettingsService.ts:58) → defaults de percents + `rounding_mode` + `main_currency_symbol`; `listCategories("product-categories", {page_size: 100})` (calcSettingsService.ts:70) → opciones del select de categoría.
- (F2, existente — para el select de materiales, vía `calcMaterialsService`): `listMaterials({q?, page_size?})` (calcMaterialsService.ts:47) → `MaterialListResponse`; el `Material` trae `unit_cost?: string` y `status` para armar el label de la opción.

**Ojo: los montos del detalle son str.** Al precargar el editor en modo edición, los inputs numéricos (cantidad, tarifa, minutos, costo, percents) se llenan con `Number(str)` **solo para el preview**; al guardar, el payload envía números propios de los inputs — los `line_total_cost`/snapshots del server jamás se reutilizan ni se mandan.

## Reglas de la UI

### Páginas
- `ProtectedRoute requiredRole="admin"` (sin sesión → `/login`, no-admin → `/unauthorized` — comportamiento existente).
- `nuevo`: editor en modo alta (form vacío, percents precargados con los defaults de `GET /calc/settings` — **1 solo GET de settings al montar en modo alta**).
- `[id]`: editor en modo edición; al montar `GET /calc/products/{id}?include_versions=true` (spinner; 404 → toast + estado vacío con botón Volver; error → toast + "Reintentar" — patrón `MaterialsAbm.tsx:100-138`).

### Layout del editor (paridad `ProductEditor.jsx` del origen, tokens DESIGN.md)
- Grid `lg:grid-cols-[1fr,320px]` (1 columna en base): columna principal = card "Datos generales" + card "Materiales (N)" + card "Mano de obra (N)" + card "Otros costos (N)"; sidebar (sticky top) = `ProductSummaryPanel` (+ `SimulationPanel` cuando está abierto).
- Header de la página con acciones: **Volver** (`router.back()`), **Simular** (toggle pill outline), **Recalcular** (solo edición), **Eliminar** (solo edición, `#e23b4a`), **Guardar** (primario, `busy` con `loading`).
- Form "Datos generales" (labels en español, `Field.Root`/`Input`/`Textarea`/`Select` como en `MaterialForm.tsx`): Nombre* (1–120), SKU (≤40), Categoría (Select de `product-categories`, opción "Sin categoría"), Descripción (≤500), Notas (≤500), Margen % / Descuento % / Impuesto % (3 `Input type=number` 0–100; fuera de rango → Guardar deshabilitado), Estado (Select draft/active/archived — "Borrador"/"Activo"/"Archivado"; default `draft` en alta, valor actual en edición).
- **Guardar deshabilitado** cuando: `name` vacío, algún percent fuera de 0–100, o alguna línea inválida (material sin seleccionar; labor/extra sin nombre; número inválido/negativo).

### Tablas de líneas (inline, paridad de las tablas del origen)
- Cada card: título con conteo `(N)`, botón **"Agregar fila"** (pill outline) que agrega una fila vacía, tabla de filas, cada fila con botón **quitar** (icono/`Button size="xs"`, danger suave). Sin filas → texto "Sin materiales/labor/costos extras." (no es error: se puede guardar un producto sin líneas).
- **Materiales** (`ProductMaterialLines`): fila = `Combobox` de material (Chakra v3) + `Input` cantidad + total de fila (preview) + quitar. El Combobox hace búsqueda **asíncrona debounced 300 ms** contra `calcMaterialsService.listMaterials({q, page_size: 50})` (debounce como `MaterialsAbm.tsx:140-147`); opciones: nombre + `— unit cost {unit_cost}` (o "— incompleto" si `status === "incomplete"`); selección → fila guarda `material_id` + nombre + `unit_cost` (str) + `unit_of_measure` (para el total preview y el label). Total de fila = `quantity × unit_cost` (preview; material incompleto → costo 0.00, igual al snapshot del servidor, D4).
- **Labor** (`ProductLaborLines`): fila = `Input` actividad (1–120) + `Input` tarifa/hora (≥0) + `Input` minutos (≥0) + total (`tarifa × minutos/60`, preview) + quitar.
- **Extra** (`ProductExtraLines`): fila = `Input` concepto (1–120) + `Input` costo unitario (≥0) + `Input` cantidad (≥0) + total (`costo × cantidad`, preview) + quitar.
- Inputs numéricos: string en estado, parse al estilo `MaterialForm.tsx:44-49` (vacío → 0 para el preview; inválido/negativo → fila inválida, no se envía). Totales/subtotales formateados con `Intl.NumberFormat("es-AR", {minimumFractionDigits: 2})` + símbolo de `settings.main_currency_symbol` (formato de presentación de números **propios del preview**; los str del servidor — versiones, costos tras recalcular — se muestran **tal cual**).

### Summary en vivo (`ProductSummaryPanel`) — decisión F3-Q2
- Siempre visible en el sidebar; se recalcula con `useMemo` ante cualquier cambio de línea o percent (RF: paridad con el origen, donde el resumen reacciona al instante).
- Contenido: subtotales Materiales / Mano de obra / Otros costos (con % de distribución sobre el costo total, barra fina como en el origen), separador, los **6 montos** del motor (Costo total en bold; Descuento negativo en `#e23b4a`; **Precio final destacado** `tabular-nums` `text-lg` con el `rounding_mode` de settings aplicado en el preview), y el label fijo **"Preview — se confirma al guardar"**.
- Los montos del preview **nunca** viajan en un payload (RF-P4CC-05). En modo edición, al precargar, el preview con los valores del servidor debe coincidir con los montos traídos (tolerancia: redondeo float vs Decimal — por eso el label).

### Simulación (`SimulationPanel`) — decisión F3-Q3
- Toggle con el botón "Simular". Panel debajo del summary: 3 inputs (Margen/Descuento/Impuesto %) inicializados con los del form (estado propio del panel — cerrarlo o cambiarlos NO muta el form), precio simulado (mismo espillo + rounding de settings) y "Diferencia vs. actual" (+ verde success / − rojo / 0 neutro). Botón cerrar (X) → panel oculto.

### Guardar / recalcular / eliminar (decisión F3-Q5)
- **Alta**: `createProduct(payload)` con payload completo: 8 campos del producto (percents siempre; `sku`/`category_id`/`description`/`notes` vacíos → omitidos) + las **3 listas de líneas siempre presentes** (`[]` si no hay). → 201: toast success "Producto creado" + `router.replace("/admin/calculadora/productos/" + response.product.id)` (el [id] recarga todo desde el servidor). → 404/422/409 (`"SKU ya en uso"`): toast con el `detail`, sin navegación, form intacto.
- **Edición**: `updateProduct(id, payload)` con los campos del form + las **3 listas siempre** (reemplazo completo, RF-P4CC-02 — no usar la semántica "clave ausente no cambia" desde el editor). → 200: toast success "Producto guardado" + **re-hidratar el estado local desde la respuesta** (líneas con snapshots/totales del servidor y percents guardados). → 404/422/409: toast con el `detail`, sin cerrar.
- **Recalcular** (solo edición): `recalculateProduct(id)` → 200: re-hidratar líneas + costs desde la respuesta + toast success ("Producto recalculado" o "Producto recalculado — precio actualizado (v{n+1})" no es distinguible sin versiones: usar "Producto recalculado") + refetch del detalle para refrescar la card de versiones (llamar de nuevo `getProduct` con `include_versions`). 404 → toast.
- **Eliminar** (solo edición): `Dialog` de confirmación (botón confirmar `#e23b4a`, patrón `MaterialsAbm.tsx:549-573`) → `deleteProduct(id)` → 204: toast success + `router.back()`. 404 → toast.
- Sin dirty-checking (F3 no lo exige; el usuario puede salir sin confirmar).

### Versiones (`ProductVersionsCard`) — solo modo edición
- Card debajo de las tablas: tabla `V# / Fecha (es-AR) / Costo / Precio` en orden desc (como llega). Montos str tal cual. Vacío → "Sin historial de versiones.".

## Patrones a seguir (ficheros de referencia reales)
- **Arquitectura de estado de un componente con carga (loading/error/cancel/reload)**: `frontend/src/components/calc/MaterialsAbm.tsx:61-138`; **debounce de búsqueda 300 ms**: `:140-147`; **handleCreate/handleSaveEdit con busy + toast**: `:192-260`; **handleDelete con diálogo**: `:261+`; **EmptyState**: `:428-435`; **Dialog.Root** de confirmación/edición: `:549-573`.
- **Form con validación client-side + parse numérico + payload**: `frontend/src/components/calc/MaterialForm.tsx:44-118` (`parseAmount` :44-49, `handleSubmit` :54-118, `assignTouchedText` :228-248); `Field/Input/Textarea/Select` Chakra v3 con `createListCollection` (:32-52).
- **Service tipado con helpers query/json/delete-204**: `frontend/src/services/calcMaterialsService.ts:16-50` (buildQuery :16-25, jsonOptions :27-29, deleteViaApiFetch :36-44) — copiar la estructura a `calcProductsService.ts`.
- **Settings/categorías existentes para reutilizar**: `frontend/src/services/calcSettingsService.ts:58` (`getSettings`), `:70` (`listCategories` con `kind: "product-categories"`).
- **Page protegida**: `frontend/src/app/admin/calculadora/materiales/page.tsx` (toda) + `frontend/src/app/admin/calculadora/configuracion/page.tsx`.
- **Test de componente mockeando services + toaster**: `frontend/src/components/calc/MaterialsAbm.test.tsx:8-48` (vi.mock, fixtures, `renderWithProviders`, helpers de interacción); `frontend/src/app/admin/calculadora/materiales/page.test.tsx` (page con mock de `useAuth`).
- **Test utils**: `frontend/src/test-utils.tsx` (`renderWithProviders`).
- **Chakra v3 compound** (paquete `@chakra-ui/react` 3.37 instalado): `Combobox.Root/Trigger/Input/Positioner/Content/Item`, `Select.Root`, `Dialog.Root/Backdrop/Positioner/Content`, `Field.Root/Label/Input`, `Button`, `Table.Root/ScrollArea`, `EmptyState`, `Spinner`, `Flex`, `Text`, `Card` (o `Box` con tokens DESIGN.md para cards outline sin shadow).
- **Paridad legacy (solo lectura, no importar)**: `E:/toscana/calculadora-costos-toscana/src/pages/ProductEditor.jsx`, `src/components/products/{ProductSummaryPanel,SimulationPanel}.jsx`, `src/pages/ProductDetail.jsx` (sección Historial de Versiones).
- **Backend (solo lectura, para types/payloads)**: `backend/src/api/v1/calc/schemas.py:358-567` (líneas In/Out, ProductCreate/Update/Response, Costs, WithLines, Version) y `router.py:1181,1418,1508,1662,1682,1718`.

## Cobertura de tests (criterios, ≥1 test por caso; total ≥20 nuevos)
Mocks: `vi.mock("@/services/calcProductsService")`, `vi.mock("@/services/calcMaterialsService")`, `vi.mock("@/services/calcSettingsService")`, `vi.mock("@/lib/toaster")`.
1. **Pages** (2): `nuevo` y `[id]` renderizan `ProtectedRoute requiredRole="admin"` (mock `useAuth`, patrón `materiales/page.test.tsx`).
2. **ProductEditor** (≥6): (a) alta: Guardar deshabilitado con name vacío y con percent > 100; (b) alta → POST payload con las 3 listas presentes, percents, `status: "draft"` por default y **sin ninguna clave `line_total_cost`/`unit_cost_snapshot`/`costs`** (aserción sobre el objeto pasado al mock); (c) POST 201 → `router.replace` a `/productos/{id}` + toast; (d) POST 409 (`"SKU ya en uso"`) → toast + sin navegación; (e) edición: al montar llama `getProduct(id, {includeVersions: true})` y precarga form/líneas (inputs con los valores); (f) edición → PATCH con las 3 listas de líneas completas (reemplazo) + re-hidrata desde la respuesta (200 → toast); (g) Recalcular → `recalculateProduct(id)` → re-hidrata líneas/costs + toast; (h) Eliminar → diálogo → `deleteProduct` 204 → toast + `router.back()`.
3. **ProductMaterialLines** (≥5): (a) "Agregar fila" agrega una fila; quitar la elimina; (b) tipear en el Combobox → `listMaterials` con `q` (debounce) y opciones renderizadas (nombre + unit cost); (c) seleccionar material → la fila muestra nombre, unidad y total de fila = cantidad × unit cost; (d) material `incomplete` → opción marcada "incompleto" y total 0.00; (e) cantidad inválida/negativa → fila inválida (el editor no habilita Guardar).
4. **ProductLaborLines / ProductExtraLines** (≥2 c/u): agregar/quitar fila; edición de campos actualiza el total de fila (labor: `tarifa × min/60`).
5. **ProductSummaryPanel** (≥2): renderiza los 6 montos + subtotales con los valores del preview; `discount_amount` negativo se muestra en rojo; precio final destacado.
6. **SimulationPanel** (≥2): cambiar un percent de simulación actualiza el precio simulado y la diferencia; cerrar oculta el panel sin mutar los percents del form.
7. **ProductVersionsCard** (≥2): renderiza versiones en orden desc (v#, fecha, cost, precio str); vacío → "Sin historial de versiones.".

## Prohibiciones (safe mode)
1. **No tocar `backend/`** en absoluto (B1–B10 DONE; los payloads se prueban contra el shape documentado arriba, no contra el backend corriendo).
2. **No tocar código ajeno**: `calcSettingsService.ts`, `calcMaterialsService.ts` (usar, no modificar), los 9 componentes F1/F2, `configuracion/*`, `materiales/*`, `src/lib/api.ts`, `src/lib/toaster.tsx`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`, settings/pricing legacy (L2: coexistencia).
3. **Nada de montos derivados en payloads** (POST/PATCH): `line_total_cost`, `material_name`, `*_snapshot`, `costs`, `final_sale_price` → 422 (`extra="forbid"`, RF-P4CC-05). Los payloads de líneas llevan solo: material `{material_id, quantity_used}`, labor `{activity_name, hourly_rate, minutes_required}`, extra `{concept_name, unit_cost, quantity}`.
4. **El espillo `lib/calcPricing.ts` es preview-only**: sus resultados jamás se mandan al servidor; los valores persistidos los produce el backend (Decimal `ROUND_HALF_UP`). No duplicar la fórmula en más de un lugar.
5. **No recalcular/derivar `unit_cost` de materiales en la UI** (F2: es solo-escritura del servidor).
6. **Sin dependencias nuevas**, sin react-query/swr (fetches directos con `apiFetch` y estado local, como F1/F2).
7. **Auth**: no implementar nada nuevo — solo `ProtectedRoute requiredRole="admin"`.
8. **No commitear ni pushar.**
9. No modificar `next.config.ts`, `eslint.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx` ni `package.json`.
10. No crear la página de lista `/admin/calculadora/productos` (index) — es **F4**; F3 solo crea `nuevo/` y `[id]/`.

## Criterio de salida (medible)
1. `GET /admin/calculadora/productos/nuevo` con sesión admin: editor en modo alta (percents precargados con defaults de settings); sin sesión → `/login`; no-admin → `/unauthorized`. `/admin/calculadora/productos/{id}`: carga el producto (líneas + 6 montos + versiones) y lo precarga en el editor.
2. Las 3 tablas permiten agregar/editar/quitar filas; el summary del sidebar se recalcula en vivo (cambiar cantidad, tarifa, percent → los 6 montos cambian sin guardar) y el label de preview está presente.
3. Alta: Guardar → POST 201 con las 3 líneas completas → toast + redirect a `/productos/{id}`. Edición: Guardar → PATCH 200 con reemplazo completo de líneas → estado re-hidratado del servidor; 409 SKU → toast "SKU ya en uso" sin navegación.
4. Simulación: panel con 3 percents + precio simulado + diferencia; cerrarlo no modifica el form.
5. Modo edición: Recalcular → 200 → líneas/costs actualizados + toast; Eliminar → diálogo → 204 → toast + volver; card de versiones desc (o "Sin historial de versiones.").
6. `npx vitest run`: baseline 46 tests (F1+F2) + ≥20 tests nuevos (secciones 1–7) todos verdes.

## Gate final (exacto, desde `frontend/`)
```
cd frontend
rm -rf .next tsconfig.tsbuildinfo
npx tsc --noEmit
npm run lint
npm run build
npx vitest run
```
→ **los 4 verdes**. Baseline verificado en esta rama (sobre `4a6b80a`, PR #33): `tsc` 0 errores **después de `rm -rf .next tsconfig.tsbuildinfo`** (el `.next` puede quedar stale de otra rama; si `tsc` falla con errores de `.next/types` que apunten a páginas inexistentes, borrar `.next` y re-ejecutar — no es error tuyo), `eslint` 0 errores, `next build` OK (10 rutas de F1+F2 + proxy), `vitest` **46 passed / 9 archivos** (F1 19 + F2 27). Al terminar: mismos 4 gates verdes con tu código (2 rutas nuevas + tests nuevos), sin tocar rutas existentes.

## Output esperado
1. Resumen: archivos nuevos/modificados, count de tests Vitest (nuevos + total), cómo quedó el summary en vivo (espillo) y la simulación, confirmación de que ningún payload lleva montos derivados.
2. Resultado literal de los 4 gates.
3. Dudas/bloqueantes.

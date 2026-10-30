# Brief F2 — Página `/admin/calculadora/materiales`: catálogo de materiales (lista, búsqueda, filtros, form, historial)

Tarea: F2 de `odd/tasks/cost-calculator.md` (T-F2). **Frontend solo** (`frontend/`); el backend (B1–B10, 528 tests) está completo y NO se toca. 1 página nueva: listado de materiales con búsqueda + 3 filtros, form de alta/edición (8 campos) y historial de costos por material.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea F2 + specs S4 (materiales, `docs/specs/p02_ingredients.md` §P2-CC) y S7 (UI admin Next.js 15 + Chakra v3 + `.claude/design/DESIGN.md`).
- `docs/specs/p02_ingredients.md` §P2-CC → RF-P2CC-01 (CRUD y campos), RF-P2CC-02 (`unit_cost` solo-escritura del servidor, nunca del cliente), RF-P2CC-03 (status derivado `incomplete` si falta precio o cantidad), RF-P2CC-04 (historial de costos paginado), RF-P2CC-05 (búsqueda `?q` nombre/código, filtros `?category_id, ?supplier_id, ?status`, paginación default 50 max 100; delete usado → 409 + `{impacted_products}`).
- Decisión ya cerrada (B8, `PREGUNTAS.md` D1): el status es **100% derivado por el servidor** con valores `active | incomplete` (NO hay `inactive` ni setter del cliente; el spec lo mencionaba pero el payload publicado lo cerró). La UI solo **muestra** el status.
- API: verificada en `backend/src/api/v1/calc/router.py` (commit `79245d6`, PR #31) + `backend/src/api/v1/calc/schemas.py` — ver sección "Endpoints" abajo. Montos/cantidades viajan como **str** (`api/v1/money.py`).
- Tokens de diseño: `C:\Users\Usuario\toscana-pastry\.claude\design\DESIGN.md` — botones pill (`rounded="full"`), cards outline 1px `{colors.hairline-light}` sin shadow, danger `#e23b4a` para acciones destructivas, `surface-soft` `#f4f4f4` para chips de estado inactivo/incompleto.
- Decisias F2 pendientes (UI): `PREGUNTAS.md` → entradas F2 (ruta de página + form de edición; presentación del historial) con decisión propuesta a respetar.

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`, rama `feat/f2-calc-materials` (ya creada y apilada sobre F1: verificar `git merge-base --is-ancestor 12085f2 HEAD` → exit 0, `12085f2` = PR #32). **NO commitear ni pushar** — el orquestador lo hace.
- Código en inglés; comentarios/docstrings en español (convención del repo).
- Stack de tests ya existe por F1 (Vitest + jsdom + Testing Library): NO tocar `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx` ni `package.json` (no se agregan dependencias).

## TDD: Vitest
Tests de componentes con `vitest` + `@testing-library/react` mockeando el **service** (`vi.mock("@/services/calcMaterialsService")`) y el toaster (`vi.mock("@/lib/toaster")`), sin backend real — mismo patrón que `frontend/src/components/calc/CategoryAbm.test.tsx:8-21`. Render siempre con `renderWithProviders` de `frontend/src/test-utils.tsx`. Baseline: **19 tests verdes de F1** que no pueden romperse.

## Alcance (archivos)
Todo bajo `frontend/`. Nada de `backend/`.

| Archivo | Cambio |
|---|---|
| `frontend/src/types/calc.ts` | EXTENDER (append, no reescribir lo existente): `MaterialStatus = "active" \| "incomplete"`; `Material` (shape de `MaterialResponse`, montos/cantidades como `string \| null`); `MaterialListResponse`; `MaterialCreatePayload` (8 campos, precio/cantidad como `number \| null` — ver Endpoints); `MaterialUpdatePayload` (todos opcionales, `null` = limpiar precio/cantidad); `CostHistoryEntry` (`{previous_unit_cost: string \| null, new_unit_cost: string \| null, changed_at: string}`); `CostHistoryListResponse`; `MaterialListQuery` (`{q?, category_id?, supplier_id?, status?, page?, page_size?}`). |
| `frontend/src/services/calcMaterialsService.ts` | NUEVO: `calcMaterialsService` con los 6 métodos (ver Endpoints). Reutilizar el patrón de `calcSettingsService.ts` (helpers privados `buildQuery`/`jsonOptions`/`deleteViaApiFetch` — copiarlos locales a este archivo; NO modificar `calcSettingsService.ts`). DELETE: el 204 con body vacío hace que `apiFetch` lance `SyntaxError` → reutilizar el mismo truco de `calcSettingsService.ts:43-50`. |
| `frontend/src/app/admin/calculadora/materiales/page.tsx` | NUEVO: `"use client"`, `ProtectedRoute requiredRole="admin"`, `Container py={10} maxW="container.xl"` (la tabla tiene ~10 columnas; la config F1 usó `container.md` pero el listado necesita ancho — decisión documentada en `PREGUNTAS.md`), `Heading` "Materiales", renderiza `<MaterialsAbm />`. Patrón de page: `frontend/src/app/admin/calculadora/configuracion/page.tsx` (solo la parte de `ProtectedRoute` + Container; no hay tabs acá). |
| `frontend/src/components/calc/MaterialForm.tsx` | NUEVO: form reutilizado para alta y edición. Props: `initial?` (material a editar), `categories` (opciones de categoría), `suppliers` (opciones de proveedor), `onSubmit(payload)`, `busy`. Campos y validaciones: ver "Form (alta/edición)". |
| `frontend/src/components/calc/MaterialsAbm.tsx` | NUEVO: listado completo — toolbar (búsqueda + 3 filtros + total), card de creación (`MaterialForm`), tabla, paginación prev/next, acciones por fila (Editar → `Dialog` con `MaterialForm`, Historial → `CostHistoryDialog`, Eliminar → `Dialog` de confirmación), `EmptyState`, estado de error con reintento. Estructura de referencia: `CategoryAbm.tsx` (ver Patrones). |
| `frontend/src/components/calc/CostHistoryDialog.tsx` | NUEVO: diálogo de historial de costos de un material (ver "Historial de costos"). |
| `frontend/src/components/calc/MaterialForm.test.tsx` | NUEVO |
| `frontend/src/components/calc/MaterialsAbm.test.tsx` | NUEVO |
| `frontend/src/components/calc/CostHistoryDialog.test.tsx` | NUEVO |
| `frontend/src/app/admin/calculadora/materiales/page.test.tsx` | NUEVO |

No se toca: `src/services/calcSettingsService.ts`, los 4 componentes F1 de `src/components/calc/`, `configuracion/page.tsx`, `src/lib/*`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`, `src/types/calc.ts` más allá del append, `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx`, `package.json`, `next.config.ts`, `eslint.config.mjs`, `tsconfig.json`.

## Endpoints a consumir (verificados en `backend/src/api/v1/calc/router.py` + `schemas.py`)
Base: `apiFetch` ya prefija `NEXT_PUBLIC_API_URL || http://localhost:8000/api/v1` (`frontend/src/lib/api.ts:45`). Todos los GET piden sesión (401); los writes son admin-only (403 no-admin).

`MaterialResponse` (schemas.py:309): `{id: string, name, internal_code?, category_id?, supplier_id?, unit_of_measure?, purchase_total_price?: string, package_quantity?: string, unit_cost?: string, notes?, status: "active" | "incomplete", created_at, updated_at}` — **solo ids, sin nombres** de categoría/proveedor (ver "Ojo: nombres de categoría/proveedor" abajo).

- `GET /calc/materials?q?,category_id?,supplier_id?,status?,page=1,page_size=50` (router.py:806) → `MaterialListResponse` `{items, total, page, page_size}` (schemas.py:325). `q`: 1–120 chars, accent-insensitive sobre **nombre e internal_code**; `page_size` 1–100.
- `POST /calc/materials` (router.py:755) — body `MaterialCreate` (schemas.py:256, `extra="forbid"`): `{name* (1–120, sin solo-blancos), internal_code? (≤40), category_id?, supplier_id?, unit_of_measure? (≤20), purchase_total_price?: num/str ≥ 0, package_quantity?: num/str > 0, notes? (≤500)}` → **201** item / **404** FK inválida (`"Categoria no encontrada"` / `"Proveedor no encontrada"`) / **422** rangos, name vacío, **o cualquier campo extra (`unit_cost`, `status`) — nunca mandarlos**.
- `GET /calc/materials/{id}` (router.py:831) → 200 item / 404.
- `PATCH /calc/materials/{id}` (router.py:850) — body `MaterialUpdate` (schemas.py:282, `extra="forbid"`): mismos 8 campos, todos opcionales (≥1 campo; body vacío → 422). **Detalle clave**: un `null` explícito en `purchase_total_price`/`package_quantity` **elimina** el dato (unit_cost → null, status → incomplete, y se registra en historial si cambió, RF-P2CC-04) — por eso el form de edición manda `null` para campos vaciados, a diferencia de los otros ABM donde vacío = no mandar. → 200 item / 404 / 404 FK / 422 (incl. `unit_cost`/`status` extra, o `package_quantity` ≤ 0).
- `DELETE /calc/materials/{id}` (router.py:924) → **204** / 404 / **409 body `{"impacted_products": N}` SIN campo `detail`** (router.py:943) → `apiFetch` (api.ts:71) lanza `Error("Network error")`. La UI usa mensaje propio (mismo patrón que F1, `CategoryAbm.tsx:206-219`).
- `GET /calc/materials/{id}/cost-history?page=1,page_size=50` (router.py:958) → `CostHistoryListResponse` (schemas.py:340): `{items: [{previous_unit_cost?: string, new_unit_cost?: string, changed_at}], total, page, page_size}`, **más recientes primero** (desc). 404 si el material no existe.

**Ojo: nombres de categoría/proveedor.** `MaterialResponse` trae solo `category_id`/`supplier_id`. La tabla MUESTRA los nombres resolviéndolos **client-side** con el id→name map de las dos listas que ya se cargan para los filtros (`GET /calc/material-categories?page_size=100` y `GET /calc/suppliers?page_size=100` — endpoints F1, vía `calcSettingsService.listCategories("material-categories", ...)` / `calcSettingsService.listSuppliers(...)`, verificados en router.py:234/493 y F1). id sin match → "—". Sin match de opción nueva: si un material referencia un id que no está en las 100 primeras opciones, se muestra el id truncado o "—" (caso límite; no bloquea).

## Reglas de la UI

### Page
- `ProtectedRoute requiredRole="admin"` (sin sesión → `/login`, no-admin → `/unauthorized` — comportamiento existente de `ProtectedRoute`).
- Encabezado "Materiales" + un solo componente `MaterialsAbm` (no hay tabs).

### Listado + toolbar (`MaterialsAbm`)
- Carga: spinner → `GET /calc/materials?page=1&page_size=50` (patrón de carga/error/cancelación de `CategoryAbm.tsx:63-98` y `admin/page.tsx:13-47`).
- **Búsqueda**: `Input` con debounce 300 ms que manda `?q` (patrón exacto `CategoryAbm.tsx:100-107`); `q` vacío → sin parámetro. Cambiar búsqueda/filtros vuelve a `page=1`.
- **Filtros** (3 `Select.Root`): Categoría (opciones del GET material-categories, opción "Todas" = sin parámetro), Proveedor (idem, "Todos"), Estado (options "Todos" / "Activo" → `status=active` / "Incompleto" → `status=incomplete` — son los únicos 2 estados, D1). Las listas de opciones se cargan **una sola vez** al montar `MaterialsAbm` (2 GETs paralelos; un error en esas cargas no rompe la lista principal — los filtros quedan con solo la opción "todos").
- **Tabla** (`Table.Root size="sm"` dentro de `Table.ScrollArea`, patrón `CategoryAbm.tsx:328-423`): columnas Nombre (con `internal_code` debajo en `fg.muted` si existe), Categoría, Proveedor, Unidad, Precio paquete, Ctd paquete, Costo unitario, Estado, Acciones. `unit_cost` y montos se muestran **tal cual el str del response** (sin formateo ni aritmética); `null` → "—". **Chip de estado**: `active` → success (token success de DESIGN.md), `incomplete` → chip con fondo `#f4f4f4` y texto "Incompleto" (read-only; nunca se envía).
- **Paginación**: prev/next + "Total: N", `page_size=50` fijo (decisión F1 de `PREGUNTAS.md`, `CategoryAbm.tsx:425-446`).
- **Vacío**: `items` vacío → `EmptyState` (`CategoryAbm.tsx:318-325`). **Error de carga**: toast danger + estado con botón "Reintentar" (`CategoryAbm.tsx:245-258`).

### Form (alta/edición) — `MaterialForm`
Campos (labels en español): Nombre* (1–120), Código interno (≤40), Categoría (Select), Proveedor (Select), Unidad de medida (≤20, ej. kg/litro/unidad), Precio del paquete (number ≥ 0), Cantidad por paquete (number > 0), Notas (≤500).
- **Alta** (card encima de la tabla, patrón `CategoryAbm.tsx:269-303`): campos vacíos → **no se mandan** (payload mínimo `{name}`); Guardar deshabilitado con nombre vacío; `package_quantity` 0 o negativo o `purchase_total_price` < 0 → no se envía (validación client-side, no depender del 422). POST → 201: toast success + fila nueva visible (append o refetch) + limpiar form; 404 FK → toast con el `detail`; 422 → toast con el `detail`.
- **Edición** (`Dialog` con el mismo `MaterialForm` precargado — decisión en `PREGUNTAS.md`): al guardar, `PATCH` con **solo los campos tocados** (comparar contra el original, patrón `CategoryAbm.tsx:149-197`), EXCEPTO precio/cantidad: input vacío → `null` explícito (limpia el dato, RF-P2CC-04) o el número escrito. Sin cambios → no enviar. 200 → toast success + fila actualizada; 404/422 → toast con el `detail` y el diálogo no se cierra.
- **Nunca** incluir `unit_cost` ni `status` en ningún payload (`extra="forbid"` → 422).

### Eliminar
Acción por fila → `Dialog` de confirmación (botón confirmar en `#e23b4a`, patrón `CategoryAbm.tsx:433-469`) → DELETE → 204: toast success + fila fuera; **409 (`"Network error"` de `apiFetch`)**: toast danger con mensaje propio "No se puede eliminar: el material está en uso en productos" (el body `{"impacted_products": N}` no es accesible sin tocar `lib/api.ts`, prohibido) + fila intacta.

### Historial de costos — `CostHistoryDialog`
Decisión propuesta (ver `PREGUNTAS.md` F2): botón "Historial" por fila → `Dialog` que al abrir hace `GET /calc/materials/{id}/cost-history?page=1&page_size=50` y muestra tabla **descendente** (más recientes primero, como el backend) con columnas: "Anterior" (`previous_unit_cost` str o "—"), "Nuevo" (`new_unit_cost` str o "—"), "Fecha" (`changed_at` formateado `es-AR`). Paginación prev/next si `total > page_size` (mismo patrón). Vacío → texto "Sin cambios de costo registrados." Error de carga → toast + reintento dentro del diálogo. Montos tal cual el str del servidor (sin aritmética).

## Patrones a seguir (ficheros de referencia reales)
- **Estructura completa de un ABM (copiar la arquitectura de estado)**: `frontend/src/components/calc/CategoryAbm.tsx` — carga con `cancelled` (:63-98), debounce 300 ms de búsqueda (:100-107), create con append (:109-141), edit con PATCH solo campos tocados (:143-197), delete con diálogo y manejo 409 "Network error" (:199-243), `EmptyState` (:318-325), paginación prev/next con `nextDisabled` (:262, :425-446), `Dialog` de confirmación con danger token (:433-469).
- **Page protegida**: `frontend/src/app/admin/calculadora/configuracion/page.tsx:1-13,44-63` (`ProtectedRoute requiredRole="admin"` + `Container`).
- **Service tipado con helpers query/json/delete-204**: `frontend/src/services/calcSettingsService.ts:18-50` (buildQuery :18-27, jsonOptions :29-31, deleteViaApiFetch :43-50).
- **Types de la API**: `frontend/src/types/calc.ts` (convención: montos `string`, payloads de update con `null` = limpiar).
- **Test de componente mockeando service + toaster**: `frontend/src/components/calc/CategoryAbm.test.tsx:8-48` (vi.mock, fixtures, `renderWithProviders`, `openDeleteConfirm` helper); `frontend/src/app/admin/calculadora/configuracion/page.test.tsx` (mock de `useAuth` para la page).
- **Test utils**: `frontend/src/test-utils.tsx` (`renderWithProviders` con `ChakraProvider value={system}`).
- **Chakra v3 compound**: `Table.Root/ScrollArea`, `Select.Root` (+ Trigger/Value/Content/Item), `Dialog.Root/Backdrop/Positioner/Content`, `Field.Root/Label/Input`, `Button`, `EmptyState`, `Spinner`, `Flex`, `Text`, `Tag` (o `Flex` con bg) para el chip de estado — paquete `@chakra-ui/react` 3.37 instalado.
- **Backend (solo lectura, para types/payloads)**: `backend/src/api/v1/calc/schemas.py:256-344` (MaterialCreate/Update/Response/List, CostHistory) y `router.py:740-990` (los 6 endpoints de materials).

## Cobertura de tests (criterios, ≥1 test por caso)
Mocks: `vi.mock("@/services/calcMaterialsService")`, `vi.mock("@/services/calcSettingsService")` (listas de filtros), `vi.mock("@/lib/toaster")`.
1. **Page**: renderiza `ProtectedRoute requiredRole="admin"` (mock `useAuth`).
2. **MaterialsAbm**: (a) lista renderiza items del GET (nombre, código, costo unitario str, categoría/proveedor por nombre resuelto del map); (b) material `incomplete` → chip "Incompleto" + costo unitario "—"; (c) búsqueda → debounce dispara el service con `q` y `page` reset a 1; (d) cada filtro manda su parámetro (`category_id` / `supplier_id` / `status`); (e) paginación: "Siguiente" incrementa page, `nextDisabled` en el último; (f) alta → POST **sin `unit_cost`/`status`** en el payload + fila nueva + limpiar form; (g) alta con `package_quantity` 0 → no dispara POST; (h) edición → PATCH con **solo campos tocados** (y `null` al vaciar precio); (i) PATCH 422 (detail) → toast error y diálogo no cierra; (j) eliminar 204 → fila fuera; (k) eliminar 409 (mock `reject Error("Network error")`) → toast danger propio + fila intacta; (l) lista vacía → `EmptyState`; (m) error de carga → toast + botón Reintentar.
3. **MaterialForm**: edición precarga los valores del material; nombre vacío → submit no llama a `onSubmit`; `purchase_total_price` < 0 → no llama a `onSubmit`.
4. **CostHistoryDialog**: al abrir hace el GET con el id correcto y renderiza filas "Anterior → Nuevo + fecha" en orden desc; vacío → "Sin cambios de costo registrados."; error → toast + reintento.
5. **MaterialsAbm (filtros)**: las listas de opciones de categoría/proveedor se cargan una sola vez al montar (no un GET por render).

## Prohibiciones (safe mode)
1. **No tocar `backend/`** en absoluto (B1–B10 DONE; los payloads se prueban contra el shape documentado arriba, no contra el backend corriendo).
2. **No tocar código ajeno**: componentes F1 de `components/calc/`, `calcSettingsService.ts`, `configuracion/page.tsx`, `src/lib/*`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`, settings/pricing legacy (L2: coexistencia), módulo legacy de stock P2 (esta página es el catálogo de costos, no inventario).
3. **`unit_cost` y `status` nunca en payloads** (POST/PATCH): son solo-lectura del servidor; el backend responde 422 (`extra="forbid"`).
4. **Sin aritmética de montos en la UI**: los str del response se muestran tal cual; `unit_cost` nunca se calcula en el cliente (RF-P2CC-02).
5. **Solo PATCH de campos tocados** en edición (el backend usa `exclude_unset`); `null` explícita solo para limpiar `purchase_total_price`/`package_quantity`.
6. **Sin dependencias nuevas**, sin react-query/swr (fetches directos con `apiFetch`, como F1).
7. **Auth**: no implementar nada nuevo — solo `ProtectedRoute requiredRole="admin"`.
8. **No commitear ni pushar.**
9. No modificar `next.config.ts`, `eslint.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `vitest.setup.ts`, `test-utils.tsx` ni `package.json`.

## Criterio de salida (medible)
1. `GET http://localhost:3000/admin/calculadora/materiales` con sesión admin renderiza encabezado "Materiales" + toolbar (búsqueda + 3 filtros + total) + tabla; sin sesión → `/login`; no-admin → `/unauthorized`.
2. Búsqueda (debounce) y los 3 filtros mandan `?q/category_id/supplier_id/status` al listado; paginación prev/next con total; `EmptyState` cuando no hay items.
3. Alta: form de 8 campos → POST 201 → fila nueva; el payload **nunca** incluye `unit_cost`/`status`. Edición: diálogo → PATCH solo campos tocados → fila actualizada; vaciar precio o cantidad manda `null` (el backend pasa el material a `incomplete` y lo registra en el historial).
4. Historial: botón por fila → diálogo con la lista desc del endpoint (prev/next si hay más de 50).
5. Eliminar: diálogo → 204 → fila fuera; 409 → toast danger "en uso en productos" + fila intacta.
6. `npx vitest run`: baseline 19 tests de F1 + ≥18 tests nuevos (secciones 1–5) todos verdes.

## Gate final (exacto, desde `frontend/`)
```
cd frontend
rm -rf .next tsconfig.tsbuildinfo
npx tsc --noEmit
npm run lint
npm run build
npx vitest run
```
→ **los 4 verdes**. Baseline verificado en esta rama (sobre `12085f2`, PR #32): `tsc` 0 errores **después de `rm -rf .next tsconfig.tsbuildinfo`** (el `.next` puede quedar stale de otra rama; si `tsc` falla con errores de `.next/types` que apunten a páginas inexistentes, borrar `.next` y re-ejecutar — no es error tuyo), `eslint` 0 errores, `next build` OK (9 rutas de F1 + proxy), `vitest` **19 passed** (F1). Al terminar: mismos 4 gates verdes con tu código (rutas nuevas + tests nuevos), sin tocar rutas existentes.

## Output esperado
1. Resumen: archivos nuevos/modificados, count de tests Vitest (nuevos + total), cómo quedó la presentación del historial y el form de edición (decisiones de `PREGUNTAS.md` ejecutadas).
2. Resultado literal de los 4 gates.
3. Dudas/bloqueantes.

# Brief F1 — Página `/admin/calculadora/configuracion`: 5 tabs con ABM inline (frontend)

Tarea: F1 de `odd/tasks/cost-calculator.md` (T-F1). **Frontend solo** (`frontend/`); el backend (B1–B10) está completo y NO se toca. 1 página (5 tabs): General + 4 ABM (categorías de materiales, categorías de productos, proveedores, costos por defecto) + configuración de Vitest + tests.

## Source de verdad
- `odd/tasks/cost-calculator.md` → tarea F1 + specs S1 (settings singleton), S2 (ABM × 4), S7 (UI Chakra v3 + DESIGN.md), S8 (Vitest para la UI).
- `docs/specs/p05_settings.md` §P5-CC → RF-P5CC-01..07 (campos, rangos, allow-lists, búsqueda `?q`, paginación `?page&page_size` default 50 max 100), RF-P5CC-08 (admin-only), **sección "UI (Chakra v3 + DESIGN.md, rol admin)"** (componentes exactos: `Tabs.Root` (5 pestañas), `Field.Root`, `Input`, `Select.Root` (rounding_mode), `Table`, `Dialog` (confirmar borrado), `Button`, `EmptyState`; layout: encabezado "Configuración de la calculadora" + tabs, lista con acciones inline editar/eliminar) y RNF-P5CC-03 ("carga < 500 ms — **1 GET por pestaña**": cada tab hace su fetch **lazy al activarse por primera vez**, no los 5 al montar).
- Tokens de diseño: `C:\Users\Usuario\toscana-pastry\.claude\design\DESIGN.md` — usar donde aplique a una app interna: botones pill (`rounded: full`), cards con outline 1px `{colors.hairline-light}` **sin shadow** (`{rounded.lg}` 20px), estados success (toast al guardar) y danger (`{colors.accent-danger}` `#e23b4a`) para borrados, `surface-soft` `#f4f4f4` para chips/estados inactivos. El DESIGN.md es de marketing (fintech); se aplican **tokens**, no las bandas negras de hero.
- API (verificada en `backend/src/api/v1/calc/router.py` — commit `79245d6`, PR #31; montos/cantidades viajan como **str** por `api/v1/money.py`): ver sección "Endpoints" abajo.
- Decisias: `PREGUNTAS.md` → entradas F1 (stack de tests, paginación UI) con decisión propuesta respetarlas.

## Árbol de trabajo
- Repo `C:\Users\Usuario\toscana-pastry`, rama `feat/f1-calc-config` (ya existe; verificar `git merge-base --is-ancestor 79245d6 HEAD` → exit 0: apilada sobre `feat/b10-recalc-pricelist-dashboard`, commit `79245d6`, PR #31). **NO commitear ni pushar** — el orquestador lo hace.
- Código en inglés; comentarios/docstrings en español (convención del repo).
- Nueva **configuración de test** (Vitest) porque el frontend no tiene ninguna hoy — decisión propuesta en `PREGUNTAS.md` (ver "Decisión propuesta de tests").

## TDD: Vitest
Tests de componentes con `vitest` + `jsdom` + `@testing-library/react`: mockear `apiFetch` (o el service) con `vi.mock`/`vi.fn`, sin backend real. Escribí tests en rojo antes del componente cuando la regla de negocio esté en el componente (ej. validación 0–100 en el form, 409 → toast danger sin borrar la fila).

## Alcance (archivos)
Todo bajo `frontend/`. Nada de `backend/`.

| Archivo | Cambio |
|---|---|
| `frontend/package.json` | APPEND devDependencies (únicas nuevas, de test): `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`; script `"test": "vitest run"`. `npm install` en `frontend/`. |
| `frontend/vitest.config.ts` | NUEVO: `environment: "jsdom"`, alias `@` → `./src` (mismo que `tsconfig.json` `paths`), `setupFiles: ["./vitest.setup.ts"]`, `include: ["src/**/*.test.{ts,tsx}"]`. |
| `frontend/vitest.setup.ts` | NUEVO: `import "@testing-library/jest-dom/vitest"`. |
| `frontend/src/types/calc.ts` | NUEVO: tipos TS de las respuestas de la API (settings, category, supplier, default-cost, list responses) — montos como `string`. |
| `frontend/src/services/calcSettingsService.ts` | NUEVO: wrappers tipados sobre `apiFetch` para los 10 endpoints (ver abajo). Patrón de referencia: `frontend/src/services/authService.ts`. |
| `frontend/src/app/admin/calculadora/configuracion/page.tsx` | NUEVO: `"use client"`, `ProtectedRoute requiredRole="admin"` (mismo patrón que `frontend/src/app/admin/page.tsx:70-83`), `Container py={10} maxW="container.md"`, Heading "Configuración de la calculadora", `Tabs.Root` con 5 `Tabs.Trigger` + `Tabs.Content`. Cada tab renderiza su componente; el fetch de cada tab es **lazy al activarse por primera vez** (RNF-P5CC-03). |
| `frontend/src/components/calc/GeneralSettingsForm.tsx` | NUEVO: tab 1 (S1). |
| `frontend/src/components/calc/CategoryAbm.tsx` | NUEVO: componente **genérico** de ABM de categorías, parametrizado por `endpoint` (`"material-categories"` \| `"product-categories"`) y `title` — lo usan los tabs 2 y 3 (mismos campos y reglas, RF-P5CC-03/04). |
| `frontend/src/components/calc/SupplierAbm.tsx` | NUEVO: tab 4 (S2/RF-P5CC-05). |
| `frontend/src/components/calc/DefaultCostsAbm.tsx` | NUEVO: tab 5 (S2/RF-P5CC-06). |
| `frontend/src/components/calc/GeneralSettingsForm.test.tsx` | NUEVO |
| `frontend/src/components/calc/CategoryAbm.test.tsx` | NUEVO |
| `frontend/src/components/calc/SupplierAbm.test.tsx` | NUEVO |
| `frontend/src/components/calc/DefaultCostsAbm.test.tsx` | NUEVO |

No se toca: `src/app/admin/page.tsx` (users legacy), `src/app/{login,profile,unauthorized}`, `src/lib/api.ts`, `src/lib/toaster.tsx`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`.

## Endpoints a consumir (verificados en `backend/src/api/v1/calc/router.py`)
Base: `apiFetch` ya prefija `NEXT_PUBLIC_API_URL || http://localhost:8000/api/v1` (`frontend/src/lib/api.ts:3`). Todos piden sesión (401 sin ella, refresh automático en `apiFetch`) y los writes son admin-only (403 no-admin).

**Settings (S1)** — `CalcSettingsResponse` (schemas.py:49):
- `GET /calc/settings` → `{business_name, main_currency_name, main_currency_symbol, default_margin_percent (str), default_discount_percent (str), default_tax_percent (str), rounding_mode}`. Nunca 404 (devuelve defaults 30/0/19/`none` si no hay fila).
- `PUT /calc/settings` — body completo (`extra="forbid"`, los 7 campos; percents 0–100) → 200 con el mismo shape; 422 si un percent fuera de rango o campo desconocido. PUT = reemplazo completo atómico (RNF: mandar SIEMPRE los 7 campos).

**Categorías (material + product, mismo shape)** — `CategoryResponse` (schemas.py:99): `{id, name, description (str|null), created_at, updated_at}`; list → `CategoryListResponse` (schemas.py:107): `{items, total, page, page_size}`.
- `GET /calc/material-categories? q?,page=1,page_size=50` (q: 1–120 chars; page_size 1–100) y `GET /calc/product-categories` (ídem).
- `POST /calc/{material,product}-categories` — `{name (1–80, sin espacios en blanco), description? (≤200)}` → 201 item / 409 `{detail:"Ya existe una categoria con ese nombre: X"}` (duplicado case-insensitive) / 422.
- `PATCH /calc/{...}-categories/{id}` — `{name?, description?}` (al menos 1 campo, body vacío → 422) → 200 item / 404 / 409 duplicado / 422.
- `DELETE /calc/{...}-categories/{id}` → 204 / 404 / **409 body `{"in_use_by": N}`** (sin campo `detail` — ver "Ojo 409" abajo).

**Suppliers** — `SupplierResponse` (schemas.py:172): `{id, name, contact_name?, phone?, email?, notes?, created_at, updated_at}`.
- `GET /calc/suppliers? q?,page,page_size` → list.
- `POST /calc/suppliers` — `{name* (1–120), contact_name? (≤120), phone? (≤30), email? (formato, ≤120), notes? (≤500)}` → 201 / 422 (ej. email inválido).
- `PATCH /calc/suppliers/{id}` — mismos campos opcionales (≥1) → 200 / 404 / 422.
- `DELETE /calc/suppliers/{id}` → 204 / 404 / 409 `{in_use_by:N}`.

**Default costs** — `DefaultCostResponse` (schemas.py): `{id, name, type ("labor"|"extra_cost"), default_unit_cost_or_rate (str, Money ≥ 0), default_quantity_or_minutes (str, Qty ≥ 0), status ("active"|"inactive"), created_at, updated_at}`.
- `GET /calc/default-costs? q?,type?,page,page_size` (filtro extra `type` por allow-list).
- `POST /calc/default-costs` — `{name* (1–120), type ("labor"|"extra_cost"), default_unit_cost_or_rate (num/str ≥ 0), default_quantity_or_minutes (num/str ≥ 0), status? (default "active")}` → 201 / 422. Montos se mandan como número o string (el backend fuerza `Decimal(str(v))`).
- `PATCH /calc/default-costs/{id}` — campos opcionales (≥1) → 200 / 404 / 422.
- `DELETE /calc/default-costs/{id}` → 204 / 404 (SIN check in-use).

**Ojo 409 "en uso"**: el body del 409 es `{"in_use_by": N}` **sin `detail`**, y `apiFetch` (api.ts:68-71) cae en el fallback `"Network error"`. En la UI, para DELETE 409 en los tabs categorías/proveedores, mostrá un toast danger con mensaje propio ("No se puede eliminar: está en uso") — no dependas del `error.message` genérico para ese caso. Los otros errores (422/409 duplicado) sí llegan con `detail` (ej. "Ya existe una categoria con ese nombre: X") y se muestran como están.

## Comportamiento por tab (criterios de aceptación)

### Tab 1 — General (S1)
- Al activarse: spinner → `GET /calc/settings` → form con `Field.Root` + `Input` por campo: `business_name` (1–120), `main_currency_name` (1–40), `main_currency_symbol` (1–8), 3 numéricos de percent (0–100, `step="0.01"`), y `Select.Root` para `rounding_mode` con **exactamente** las 4 opciones `none | integer | multiple_10 | commercial_99` (labels en español).
- Validación client-side: percent fuera de 0–100 o campo requerido vacío → el botón Guardar no envía (no depende del 422 del backend para eso).
- Guardar: `PUT` con los 7 campos → toast success "Configuración guardada"; error → toast danger con el `detail`.

### Tabs 2–5 — ABM (S2), patrón común (CategoryAbm genérico, SupplierAbm, DefaultCostsAbm)
- Al activarse por primera vez: spinner → `GET` del list (`page=1, page_size=50`) → tabla (`Table.Root` size="sm" dentro de `Table.ScrollArea`, patrón `frontend/src/app/admin/page.tsx:57-90`).
- **Búsqueda**: `Input` de texto que manda `?q` (debounce ~300 ms o botón Buscar; elegir uno, fijarlo en todos los tabs); `q` vacío → lista completa.
- **Paginación**: controls prev/next + "total N" (decisión propuesta F1 en `PREGUNTAS.md`); `total`/`page`/`page_size` del response.
- **Crear**: formulario inline (fila o card encima de la tabla) con los campos del endpoint → `POST` → toast success + la nueva fila visible (append al listado o refetch) + limpiar form.
- **Editar**: acción inline por fila (botón) → campos editables en la fila o card → `PATCH` con SOLO los campos tocados (el backend acepta `exclude_unset`; ≥1 campo) → toast success + refetch de la fila/lista.
- **Eliminar**: acción inline → `Dialog` de confirmación (`{colors.accent-danger}` para el botón de confirmar) → `DELETE` → 204: toast success + fila fuera; 409: toast danger "en uso", fila intacta.
- **Vacío**: sin items → `EmptyState` (o texto equivalente con `color="fg.muted"`) — no tabla rota.
- **Error de carga** (GET): toast danger + estado reintentable (botón Reintentar o re-mount al volver al tab) — patrón de error del `AdminUsers` (`frontend/src/app/admin/page.tsx:22-40`).
- **Default costs (tab 5) específico**: `type` y `status` como selects con allow-lists; montos/quantities como inputs numéricos ≥ 0 (se mandan como número; en pantalla se muestra el `str` del response, 2 decimales).

### Page (común)
- Sin sesión → redirect `/login`; sesión no-admin → redirect `/unauthorized` (comportamiento de `ProtectedRoute`, ya cubierto por su diseño — testear al menos que la page renderiza `ProtectedRoute` con `requiredRole="admin"`).

## Patrones a seguir (ficheros de referencia reales)
- **Carga/error/cancelación** (el patrón del repo, copiarlo): `frontend/src/app/admin/page.tsx:13-47` — `useState` data/loading, `useEffect` con flag `cancelled`, `apiFetch<T>`, catch → `toaster.create({title, description: error.message, type:"error"})`, `finally` → setLoading(false).
- **Protección de ruta**: `frontend/src/components/auth/ProtectedRoute.tsx` (uso: `frontend/src/app/admin/page.tsx:70-83`).
- **API client**: `frontend/src/lib/api.ts` — `apiFetch<T>(endpoint, options)` (líneas 46-77): lanza `Error(detail)` en no-OK; no reescribirlo.
- **Service tipado**: `frontend/src/services/authService.ts`.
- **Toaster**: `frontend/src/lib/toaster.tsx` (`toaster.create`).
- **Chakra v3 Table**: `frontend/src/app/admin/page.tsx:57-90`; **theme tokens**: `frontend/src/components/ui/theme.ts` (si necesitás un color nuevo usá tokens del DESIGN.md con hex directo, no sombras).
- **Chakra v3 compound**: `Tabs.Root/List/Trigger/Content`, `Field.Root/Label/Input`, `Select.Root` (+ Trigger/Value/Content/Item), `Dialog.Root/Backdrop/Positioner/Content`, `Button`, `EmptyState` — documentación del paquete `@chakra-ui/react` 3.37 instalado.
- **Backend (solo lectura, para types)**: `backend/src/api/v1/calc/schemas.py` (CalcSettingsResponse:49, CategoryResponse:99, SupplierResponse:172, DefaultCostResponse:215) y `router.py` (GET settings:176, PUT settings:196, categories:234-340, suppliers:493-600, default-costs:624-735).

## Decisión propuesta de tests (ver `PREGUNTAS.md`)
Stack: `vitest` + `jsdom` + `@testing-library/react` + `@testing-library/jest-dom` (dev-only). `npm run test` = `vitest run`. Tests por componente mockean el **service** (`vi.mock("@/services/calcSettingsService")`), no `fetch`. Cobertura mínima de casos (≥ 1 test por caso):
1. General: renderiza valores de un GET mockeado; guard armar el PUT con los 7 campos; percent 150 → no dispara PUT; 422 mockeado → toast error.
2. CategoryAbm (correr para el endpoint `material-categories`; el de producto reusa el componente): lista renderiza items del GET; crear → POST con `{name, description}` y la fila nueva aparece; editar → PATCH con los campos tocados; eliminar → POST-confirmation: DELETE 204 quita la fila, DELETE 409 → toast danger y fila intacta; lista vacía → empty state; error de carga → toast error.
3. SupplierAbm: crear con los 5 campos; email inválido → 422 → toast con `detail`.
4. DefaultCostsAbm: crear con `type`/`status` por allow-list y montos ≥ 0 (monto negativo → no dispara POST).
5. Page: renderiza `ProtectedRoute` con `requiredRole="admin"` (mockear `useAuth`).

## Prohibiciones (safe mode)
1. **No tocar `backend/`** en absoluto (B1–B10 DONE; la paridad de payloads se prueba contra el shape documentado arriba, no contra el backend corriendo).
2. **No tocar código ajenos**: `src/app/admin/page.tsx` (users), login/profile/unauthorized, `src/lib/*`, `src/contexts/*`, `src/components/{auth,layout,profile,ui}/*`, settings/pricing legacy (L2: coexistencia).
3. **Money como string en types**: los montos/quantities de la API son `string` (serialización `api/v1/money.py`); no convertir a `float` para "aritmética" (no hay aritmética de precios en F1 — eso es F3); al editar un default cost, el input numérico manda el número que el usuario escribió.
4. **PUT settings = reemplazo completo**: nunca mandar payload parcial ni campos fuera de los 7 (`extra="forbid"` → 422).
5. **Solo dependencias de test** (`vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`). Nada de UI libraries nuevas, nada de react-query/swr (los fetches son directos con `apiFetch` como en el resto del app).
6. **Auth**: no implementar auth nueva — solo `ProtectedRoute requiredRole="admin"`.
7. **No commitear ni pushar.**
8. No modificar `next.config.ts`, `eslint.config.mjs` ni `tsconfig.json` salvo que el setup de Vitest lo exija de forma mínima (el alias `@` ya existe en tsconfig; replicarlo en `vitest.config.ts`).

## Criterio de salida (medible)
1. `GET http://localhost:3000/admin/calculadora/configuracion` con sesión admin renderiza encabezado "Configuración de la calculadora" + 5 tabs (General, Categorías de materiales, Categorías de productos, Proveedores, Costos por defecto); sin sesión → `/login`; no-admin → `/unauthorized`.
2. Al montar, se disparan **0** requests; cada tab hace **1 GET** al activarse por primera vez (RNF-P5CC-03).
3. Tab General: valores del GET editables, `rounding_mode` con las 4 opciones exactas, guard → PUT con 7 campos → toast success; percent 150 → sin PUT.
4. Cada ABM: create → 201 + fila nueva; edit → PATCH → fila actualizada; delete → diálogo → 204 → fila fuera; delete 409 → toast danger + fila intacta; búsqueda `?q` filtra; paginación prev/next con total.
5. `npx vitest run`: ≥ 15 tests verdes cubriendo los casos de "Decisión propuesta de tests".

## Gate final (exacto, desde `frontend/`)
```
cd frontend
npm install                 # solo si agregaste las devDeps de test
npx tsc --noEmit
npm run lint
npm run build
npx vitest run
```
→ **los 4 verdes**. Baseline verificado en esta rama (commit docs sobre `79245d6`): `tsc` 0 errores **después de `rm -rf .next tsconfig.tsbuildinfo`** (el `.next` que había era stale de otra rama y referenciaba `src/app/(portal)` inexistente — si `tsc` falla con errores de `.next/types` que apunten a páginas inexistentes, borrar `.next` y re-ejecutar; no es error tuyo), `eslint` 0 errores, `next build` OK (5 rutas + proxy). `vitest` no existe en el baseline (se agrega en esta tarea). Al terminar: mismos 4 gates verdes con tu código, sin tocar rutas existentes.

## Output esperado
1. Resumen: archivos nuevos/modificados, count de tests Vitest, cómo quedó la paginación/búsqueda (decisión fijada).
2. Resultado literal de los 4 gates.
3. Dudas/bloqueantes.

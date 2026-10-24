# Fase 4 — Frontend: sección admin (Ingredientes + Configuración)

> Definición de implementación. Verbose a propósito: cada decisión trae su
> racional, cada módulo su API pública, cada flujo su secuencia de estado.
> El backend (Fase 4) ya está desplegado y verificado; este doc describe cómo
> se construye el frontend sobre ese contrato.

## 1. Objetivo y alcance

### Objetivo
Pantallas admin operativas para gestionar **ingredientes** (listado,
búsqueda, CRUD, ajuste de stock, movimientos, eliminación con impacto,
importación por lista) y **configuración de negocio** (form completa con
toggles dependientes y restaurar defaults).

### En alcance
- Rutas: `/admin/ingredients`, `/admin/ingredients/new`,
  `/admin/ingredients/[id]` (detalle), `/admin/ingredients/[id]/edit`,
  `/admin/settings`.
- Refactor del admin existente: layout de sección con navegación
  Usuarios / Ingredientes / Configuración (la página de usuarios sigue en
  `/admin`, intacta en comportamiento).
- Capa de tipos TS espejo 1:1 del contrato backend.
- Capa de servicios tipados por módulo.
- Hooks de estado por módulo (listado, detalle, settings).
- Formularios con react-hook-form + zod.
- Infra de tests: Vitest + Testing Library (unit de lógica pura y
  componentes pequeños).
- Mejora del cliente API: `ApiError` con `status` y `payload` (backward
  compatible).

### Fuera de alcance (fases siguientes)
- Productos, órdenes, presupuestos, PDF, WhatsApp (P3+).
- UI del endpoint `/pricing/preview` (viene con el módulo de productos).
- E2E (Playwright) y eventos GA4 (hardening Fase 4 del plan maestro).
- Virtualización de listas: la paginación a 50 ya cubre RF-P2-01
  ("virtualización (500 ingredientes) o paginación" — se elige paginación).

## 2. Contexto y restricciones

### Backend (contrato inmutable para esta fase)
| Endpoint | Método | Notas |
|---|---|---|
| `/api/v1/ingredients` | GET | `q` (substring case-insensitive, ≤120), `status`, `page`, `page_size` (≤100, default 50) |
| `/api/v1/ingredients` | POST | `extra="forbid"`; 201; 422 payload inválido; 400 dominio. No hay unique de nombre: no existe 409 por duplicado |
| `/api/v1/ingredients/{id}` | GET | con `include_movements=true` trae los **últimos 50** movimientos |
| `/api/v1/ingredients/{id}` | PATCH | `name`, `unit`, `price_per_unit`, `low_stock_threshold`; stock **no** por acá |
| `/api/v1/ingredients/{id}` | DELETE | 204 sin cuerpo; 409 `{"impacted_recipes": N}` si hay recetas activas (borrado suave) |
| `/api/v1/ingredients/{id}/stock` | POST | `delta` (firmado), `reason: compra\|merma\|ajuste`, `ref?`; 200; **400** si el stock quedaría negativo |
| `/api/v1/ingredients/{id}/movements` | GET | paginado |
| `/api/v1/ingredients/import` | POST | `lines[]` ≤500 → `{created, errors:[{line,message}]}` |
| `/api/v1/tenant/settings` | GET | devuelve la config o los defaults del sistema (RF-P5-03); requiere auth |
| `/api/v1/tenant/settings` | PUT | atómico (RF-P5-05); 422 por rangos y dependencias; **403** si no es admin |
| `/api/v1/pricing/preview` | POST | existe, se usa en fase de productos |

Detalles de serialización que condicionar los tipos TS:
- `Money` y `Qty` viajan como **string** en JSON (Decimal → str). El
  frontend acepta `string | number` en inputs de escritura y **envía
  number** (el backend coerza), pero **formatea string** al mostrar.
- Unidades: `"kg" | "g" | "L" | "ml" | "unidad"`.
- Reasons de stock: `"compra" | "merma" | "ajuste"` (minúsculas). El stock
  inicial (alta e importación) se registra como `compra` con `ref="inicial"`;
  no hay motivo "inicial" ni "descarte" en el contrato.
- Estados: `"OK" | "LOW" | "EMPTY"` (computado por el servidor).
- `IngredientResponse` **no** trae timestamps; `StockMovementResponse`
  sí (`created_at` ISO).
- Settings: `hourly_rate` 0.01–100000; `margin_pct` 0–100; `round_step`
  0.01–1000; `gas_pct`/`waste_pct`/`urgent_surcharge_pct` 0–100;
  `default_prep_minutes` 0–1440; `default_servings` 1–999;
  `default_difficulty: "simple" | "intermedio" | "complejo"`.
  Dependencias (422): `gas_pct == 0` si `include_gas` off; `waste_pct == 0`
  si `include_waste` off.
- PUT de settings es **atómico**: el payload siempre debe llevar los 12
  campos. Enviar un subconjunto resetea los ausentes a defaults.

### Frontend existente
- Next.js **16.4.1** (App Router, `cacheComponents` + `partialPrefetching`
  ON por default en Next 16 — ver §3 D1).
- React 19, Chakra UI **v3** (`@chakra-ui/react` 3.37, tokens
  `brand.*`, `fg.muted`, `colorPalette`).
- Sesión: cookie `toscana_token` + `toscana_refresh`; cliente central
  `lib/api.ts` con refresh-token rotation (401 → refresh → retry).
- RBAC: `proxy.ts` (server, 302), `ProtectedRoute` (client,
  `requiredRole`), backend 403/404 (última línea).
- Toasts: `lib/toaster.tsx` (chakra v3 `Toaster`).
- Convenciones de código del repo: archivos de componentes PascalCase
  (`LoginForm.tsx`), utilidades camelCase (`api.ts`), directorios
  minúsculos.

### Decisiones de dependencias (aprobadas)
- `zod@^4` — validación de forms (spec p02, checklist #18).
- `react-hook-form@^7` + `@hookform/resolvers@^5` — estado de forms
  (checklist #18).
- `vitest@^4`, `@testing-library/react@^16` (+ `jest-dom`, `user-event`,
  `dom`), `jsdom@^30` — tests (checklist #3, spec p02/p05).

## 3. Decisiones de arquitectura

### D1 — Data en client components; server components solo shells
El admin es una app de sesión autenticada contra una API externa (FastAPI,
origin distinto, cookie + Bearer con refresh rotation).

- **Decisión:** las páginas `src/app/admin/**` son server components
  mínimos (metadata, headings estáticos, composición). Toda interacción y
  data vive en client components dentro de `src/modules/**`.
- **Racional:** llevar el fetch al server (RSC o Server Actions) duplicaría
  la lógica de refresh-token que ya vive en `lib/api.ts` (el server tendría
  que leer la cookie, reintentar tras 401, y además lidiar con el nuevo
  `cacheComponents` de Next 16 optando-out cada mutación). No hay base de
  datos del lado de Next; el "servidor" que tiene los datos es FastAPI.
  RSC gana caché cuando el dato vive del lado de Next; acá no vive.
- **Alternativa descartada:** Server Actions por endpoint — más round-trips
  mentales, cero beneficio de caché, y el contrato error/409/422 quedaría
  duplicado en dos capas.

### D2 — Módulo por pantalla: `src/modules/<feature>/`
- **Decisión:** cada feature admin es un módulo autocontenido:
  `types.ts` (contrato), `schema.ts` (zod), `service.ts` (llamadas
  tipadas), `hooks/` (estado), `components/` (presentación).
- **Racional:** el plan maestro manda módulos por pantalla; el repo
  actual usaba `components/` + `services/` globales, que no escala más
  allá de auth. Los nuevos features van a `src/modules/*`; lo existente
  (auth, profile, layout, ui) se mantiene hasta su fase de refactor.
- **Regla de import:** un módulo nunca importa de otro módulo (comparten
  solo `lib/*` y `components/ui|layout` app-wide).

### D3 — Estado: hooks custom, sin store
- **Decisión:** `useIngredients()`, `useIngredientDetail(id)`,
  `useSettings()`. Cada hook expone **métodos nombrados**, no "state mágico".
- **Racional:** los tres estados son independientes, de ciclo de vida de
  página. Un store (zustand) agregaría un eje de acoplamiento sin ganar
  nada: no hay estado que cruce pantallas.

### D4 — Validación: zod espejo del contrato backend
- **Decisión:** `schema.ts` por módulo refleja los validadores del
  backend (rangos, enums, dependencias de toggles, "al menos un campo" en
  update). `zodResolver` en RHF.
- **Racional:** la primera línea de validación es el cliente (latencia,
  UX); la última siempre es el backend (422 → errores inline). El espejo
  se mantiene por conveniencia del equipo, no por magia: si el backend
  cambia un rango, el test del schema frontend lo marca (y la spec manda
  sincronizarlos).
- `extra="forbid"` en el backend ⇒ los schemas zod usan
  `z.object(...).strict()` para que un typo de campo muera en cliente.

### D5 — `ApiError` en el cliente API
- **Decisión:** `lib/api.ts` tira `ApiError extends Error` con `status` y
  `payload` (el JSON del body de error) en vez de `Error` plano.
  Backward compatible: sigue siendo `instanceof Error` y `.message` sigue
  siendo `detail || message`.
- **Racional:** hoy el 409 de delete (`{"impacted_recipes": N}` — sin
  `detail`) llega como `"Network error"`. El flujo de delete con impacto
  (RF-P2-06) necesita el `impacted_recipes` del body.

### D6 — Formato es-AR centralizado y puro
- **Decisión:** `lib/format.ts` con funciones puras
  (`formatMoney`, `formatQty`, `formatSignedQty`, `formatDateTime`)
  sobre `Intl` (es-AR). Sin estado, sin Chakra.
- **Racional:** RF-P2-06 exige "$3.000"; si cada componente arma su
  `Intl.NumberFormat` a mano, el formato se fragmenta. Puro ⇒ testeable
  sin DOM.

### D7 — RBAC: las 3 capas existentes, sin inventar nada
`proxy.ts` (302 a /login) → `ProtectedRoute requiredRole="admin"` (client,
302 a /) → backend 403/404. El layout de `/admin` aplica `ProtectedRoute`
una sola vez; las subrutas heredan.

### D8 — Tests: Vitest + Testing Library sobre lógica pura y componentes pequeños
- **Decisión:** unit tests de lo que tiene lógica (format, schemas zod,
  debounce, service→URL/payload, badge de estado, dependencias de
  toggles). Sin E2E en esta fase.
- **Racional:** lo caro de testear (integración API, sesiones) ya está
  cubierto por los tests de integración del backend (pytest, 72 tests).
  El frontend aporta tests donde vive su propia lógica.

## 4. Estructura de archivos (objetivo)

```
frontend/
├── vitest.config.ts                     # NEW: esbuild jsx=automatic, jsdom
├── vitest.setup.ts                      # NEW: @testing-library/jest-dom/vitest
├── src/
│   ├── app/                             # ROUTES: shells server
│   │   └── admin/
│   │       ├── layout.tsx               # NEW: ProtectedRoute + metadata + AdminNav
│   │       ├── page.tsx                 # (existe) usuarios — sin cambios de lógica
│   │       ├── ingredients/
│   │       │   ├── page.tsx             # NEW: shell → <IngredientsPage/>
│   │       │   ├── new/
│   │       │   │   └── page.tsx         # NEW: shell → <IngredientFormPage mode="create"/>
│   │       │   └── [id]/
│   │       │       ├── page.tsx         # NEW: shell → <IngredientDetailPage id/>
│   │       │       └── edit/
│   │       │           └── page.tsx     # NEW: shell → <IngredientFormPage mode="edit"/>
│   │       └── settings/
│   │           └── page.tsx             # NEW: shell → <SettingsPage/>
│   ├── components/
│   │   └── layout/
│   │       └── AdminNav.tsx             # NEW: Tabs de sección (client, usePathname)
│   ├── lib/
│   │   ├── api.ts                       # MOD: + ApiError (status, payload)
│   │   └── format.ts                    # NEW: money/qty/signed/date es-AR (puras)
│   └── modules/
│       ├── shared/
│       │   ├── EmptyState.tsx           # NEW: vacío con CTA (p02 UI)
│       │   └── useDebounce.ts           # NEW: debounce genérico (250ms)
│       ├── ingredients/
│       │   ├── types.ts                 # NEW: contrato TS (espejo backend)
│       │   ├── schema.ts                # NEW: zod create/update/stock/import
│       │   ├── service.ts               # NEW: ingredientsService (apiFetch)
│       │   ├── hooks/
│       │   │   ├── useIngredients.ts    # NEW: listado + búsqueda + paginación
│       │   │   └── useIngredientDetail.ts # NEW: detalle + stock optimistic + delete
│       │   └── components/
│       │       ├── StockBadge.tsx       # NEW: OK/LOW/EMPTY (texto + color)
│       │       ├── IngredientsPage.tsx  # NEW: orquesta listado
│       │       ├── IngredientFormPage.tsx   # NEW: create/edit (RHF+zod)
│       │       ├── IngredientDetailPage.tsx # NEW: tabs resumen/movimientos
│       │       ├── StockDrawer.tsx      # NEW: ajuste de stock
│       │       ├── DeleteIngredientDialog.tsx # NEW: confirm + impacto 409
│       │       ├── ImportDialog.tsx     # NEW: carga por lista (RF-P2-07)
│       │       └── MovementsList.tsx    # NEW: timeline simple
│       └── settings/
│           ├── types.ts                 # NEW
│           ├── schema.ts                # NEW: zod + DEFAULTS (RF-P5-04)
│           ├── service.ts               # NEW: settingsService
│           ├── hooks/
│           │   └── useSettings.ts       # NEW: load/dirty/save/422→field errors
│           └── components/
│               └── SettingsPage.tsx     # NEW: form seccionado
│   └── (existing) contexts/, services/, components/{auth,profile,ui}/
│
│   Tests (colocados junto al código):
│   ├── src/lib/format.test.ts
│   ├── src/modules/ingredients/schema.test.ts
│   ├── src/modules/ingredients/service.test.ts
│   ├── src/modules/ingredients/components/StockBadge.test.tsx
│   ├── src/modules/settings/schema.test.ts
│   └── src/modules/shared/useDebounce.test.tsx
```

## 5. Contratos TS (`types.ts` por módulo)

```ts
// modules/ingredients/types.ts
export const INGREDIENT_UNITS = ["kg", "g", "L", "ml", "unidad"] as const;
export type IngredientUnit = (typeof INGREDIENT_UNITS)[number];

export const STOCK_REASONS = ["compra", "merma", "ajuste"] as const;
export type StockReason = (typeof STOCK_REASONS)[number];

export type IngredientStatus = "OK" | "LOW" | "EMPTY";

// Money/Qty → string en JSON (Decimal del backend)
export interface Ingredient {
  id: string;
  name: string;
  unit: IngredientUnit;
  price_per_unit: string;
  stock_qty: string;
  low_stock_threshold: string;
  status: IngredientStatus;
}

export interface Paginated<T> { items: T[]; total: number; page: number; page_size: number; }

export interface IngredientListParams {
  q?: string; status?: IngredientStatus; page?: number; page_size?: number;
}

export interface IngredientCreateInput {
  name: string; unit: IngredientUnit; price_per_unit: number;
  stock_qty?: number; low_stock_threshold?: number;
}

export interface IngredientUpdateInput {
  name?: string; unit?: IngredientUnit; price_per_unit?: number;
  low_stock_threshold?: number;   // unit SÍ es editable por PATCH
}

export interface StockAdjustInput { delta: number; reason: StockReason; ref?: string; }

export interface StockMovement {
  id: string; qty_delta: string; reason: StockReason; ref: string | null; created_at: string;
}

export interface StockAdjustmentResponse {
  stock_qty: string;
  movement: StockMovement;
}

export interface DeleteImpact { impacted_recipes: number; }

export interface ImportErrorItem { line: number; message: string; }
export interface ImportResponse { created: number; errors: ImportErrorItem[]; }
```

```ts
// modules/settings/types.ts
export type Difficulty = "simple" | "intermedio" | "complejo";

export interface BusinessSettings {
  hourly_rate: string;       // Money
  margin_pct: string;        // Money
  round_step: string;        // Money
  include_labor: boolean;
  include_gas: boolean;
  gas_pct: string;           // Money
  include_waste: boolean;
  waste_pct: string;         // Money
  urgent_surcharge_pct: string; // Money
  default_prep_minutes: number;
  default_servings: number;
  default_difficulty: Difficulty;
}

// Valores de form: number en place de string (RHF valueAsNumber)
export interface SettingsFormValues {
  hourly_rate: number; margin_pct: number; round_step: number;
  include_labor: boolean; include_gas: boolean; gas_pct: number;
  include_waste: boolean; waste_pct: number;
  urgent_surcharge_pct: number;
  default_prep_minutes: number; default_servings: number;
  default_difficulty: Difficulty;
}
```

## 6. Métodos públicos por módulo

### `lib/format.ts` (puras)
| Método | Comportamiento | Ejemplos |
|---|---|---|
| `formatMoney(v: string \| number): string` | ARS es-AR: $ + separador de miles `.`, decimales coma (0 si entero) | `"3000"`→`"$3.000"`, `"12.5"`→`"$12,50"` |
| `formatQty(v: string \| number, unit: string): string` | qty sin ceros sobrantes + unidad | `"5.0" kg`→`"5 kg"`, `"2.5" kg`→`"2.5 kg"` |
| `formatSignedQty(v: string \| number): string` | delta firmado | `2.5`→`"+2.5"`, `-1`→`"−1"` |
| `formatDateTime(iso: string): string` | es-AR fecha media + hora corta | `"2026-10-16T15:03:00Z"`→`"16/10/2026, 12:03"` |

### `lib/api.ts` (modificación aditiva)
```ts
export class ApiError extends Error {
  constructor(public status: number, message: string, public payload: unknown = null)
}
// apiFetch: en !ok → parsea el JSON del body →
//   ApiError(status, detail || message || fallback, payload)
// Sigue tirando en 401 sin refresh posible; el resto del código no cambia.
```

### `modules/shared`
- `useDebounce<T>(value: T, delayMs = 250): T` — RF-P2-02 (250ms).
- `<EmptyState title description action?/>` — vacío con CTA opcional
  (p02: "Cargá tu primer ingrediente").

### `modules/ingredients/service.ts`
```ts
export const ingredientsService = {
  list(params?: IngredientListParams): Promise<Paginated<Ingredient>>,
  getDetail(id: string, includeMovements = true): Promise<{ ingredient: Ingredient; movements: StockMovement[] | null }>,
  listMovements(id: string, page?: number): Promise<Paginated<StockMovement>>,
  create(input: IngredientCreateInput): Promise<Ingredient>,          // 201; 422/400 → ApiError
  update(id: string, input: IngredientUpdateInput): Promise<Ingredient>,
  remove(id: string): Promise<void>,                                   // 204; 409 → ApiError{impacted_recipes}
  adjustStock(id: string, input: StockAdjustInput): Promise<StockAdjustmentResponse>,
  importLines(lines: string[]): Promise<ImportResponse>,
}
```
Todos los métodos: base `/api/v1/ingredients`, auth por cookie
(`credentials: include`), payload JSON. **Sin lógica de UI** (los hooks la
pisan).

### `modules/ingredients/hooks/useIngredients.ts`
```ts
export function useIngredients() {
  // estado
  items: Ingredient[]; total: number; page: number;
  query: string;                    // valor del input (sin debounce)
  loading: boolean; error: string | null;
  // métodos
  setQuery(q: string): void;        // resetea a página 1
  goToPage(p: number): void;
  reload(): void;
  // interno: useDebounce(query, 250) dispara el fetch con page_size=50
}
```

### `modules/ingredients/hooks/useIngredientDetail.ts`
```ts
export function useIngredientDetail(id: string) {
  ingredient: Ingredient | null; movements: StockMovement[];
  loading: boolean; error: string | null;
  // La edición la hace el formulario (form → service.update → redirect);
  // el detalle expone solo las acciones que ocurren in situ.
  adjustStock(delta: number, reason: StockReason, ref?: string): Promise<AdjustStockResult>;
    // AdjustStockResult { ok: boolean; message?: string } — el 400 del backend
    // (stock insuficiente) se muestra tal cual en el drawer
    // optimista (RF-P2-03): aplica new_stock al estado, rollback en error
  remove(): Promise<"deleted" | DeleteImpact>;   // 409 → {impacted_recipes}
  reload(): void;
}
```

### `modules/settings/service.ts`
```ts
export const settingsService = {
  get(): Promise<BusinessSettings>,           // backend responde defaults si no hay config
  update(values: SettingsFormValues): Promise<BusinessSettings>,  // PUT atómico, 12 campos
}
```

### `modules/settings/hooks/useSettings.ts`
```ts
export function useSettings() {
  settings: SettingsFormValues | null;  // null hasta el GET
  loading: boolean; saving: boolean; error: string | null;
  fieldErrors: Partial<Record<keyof SettingsFormValues, string>>; // 422 → por campo
  save(values: SettingsFormValues): Promise<boolean>;
}
```
"Restaurar defaults" no es un método del hook: es acción local del form
(setValues con `SETTINGS_DEFAULTS`), porque no toca el servidor.

### Schemas zod (resumen de reglas — espejo backend)
| Schema | Reglas |
|---|---|
| `ingredientCreateSchema` | name: trim, 1–120, no solo espacios; unit: enum; price_per_unit: number > 0 (o ≥0 según backend: `ge=0` → permitir 0); stock_qty/threshold: number ≥ 0 (default 0) |
| `ingredientUpdateSchema` | todos opcionales; **al menos un campo presente** (model_validator del backend) |
| `stockAdjustSchema` | delta: number ≠ 0 (el backend no lo prohíbe; un ajuste de 0 es ruido — lo rechazamos en cliente); reason: enum; ref: string ≤120 opcional |
| `importLinesSchema` | array 1–500 de strings (líneas no vacías) |
| `settingsSchema` | rangos exactos del backend; `superRefine`: `include_gas=false ⇒ gas_pct===0`; `include_waste=false ⇒ waste_pct===0` |
| `SETTINGS_DEFAULTS` | hora $3.000, margen 30, redondeo 100, toggles ON, gas 3, merma 3, urgencia 20, prep 30, servings 6, difficulty simple (RF-P5-04) |

## 7. Flujos de data

### 7.1 Listado + búsqueda (RF-P2-02)
```
input change → setQuery(q) [estado inmediato del input]
            → useDebounce 250ms → [debouncedQuery, page] → GET /ingredients?q=&page=&page_size=50
            → setItems/setTotal
query cambia → page resetea a 1
```
Estado de carga: skeleton en tabla (Spinner + "Cargando…"), nunca disable
el input. Error de red: Alert con retry.

### 7.2 Ajuste de stock optimista (RF-P2-03)
```
submit drawer → validar (zod) → newStock = stock_qty + delta
             → setState optimista (stock_qty=newStock, status recalculado local*)
             → POST /stock
  ok      → confirmar con respuesta del servidor (stock_qty canónico)
  422/500 → rollback a stock previo + toast de error
  404     → reload del detalle (el ingrediente no existe más)
* el estado lo trae el servidor; local solo estimamos la display del
  badge (OK/LOW/EMPTY por comparación stock vs threshold).
```

### 7.3 Delete con impacto (RF-P2-06)
```
Dialog confirm → DELETE
  204 → toast + redirect /admin/ingredients
  409 → dialog muestra "En uso por N recetas activas.
        Resolvé esas recetas antes de eliminar." y bloquea el botón
        (payload.impacted_recipes vía ApiError)
```

### 7.4 Settings (RF-P5)
```
mount → GET /settings (o defaults) → hydrate form
watch(include_gas) → false ⇒ setValue(gas_pct, 0) + deshabilitar input (RF-P5-06)
dirty = formValues !== loadedValues
save  → PUT (SIEMPRE los 12 campos) → ok: toast + reload de form
                        → 422: detail[] → fieldErrors inline (campo + msg)
```

## 8. UI por pantalla (Chakra v3)

### Layout `/admin`
- Server component: `<ProtectedRoute requiredRole="admin">` + `metadata`.
- `AdminNav` (client): `Tabs.Root` horizontal — Usuarios / Ingredientes /
  Configuración; activo por `usePathname()` (exact para `/admin`, prefix
  para el resto). Mobile: mismo Tabs, scrollable.

### Listado ingredientes
- Header: título + total ("142 ingredientes") + `Button primary asChild`
  "+ Nuevo" → `/admin/ingredients/new` + `Button ghost` "Importar"
  (abre `ImportDialog`).
- Búsqueda: `InputGroup` con icono, placeholder "Buscar por nombre…".
- Desktop (`Table.Root`): Nombre · Precio unid. · Stock · Estado ·
  (acción: link "Ver"). Fila entera clicable.
- Mobile: cards (`Flex` por ítem) — mismo contenido, target ≥44px.
- Estados: `StockBadge` (colorPalette success/warning/danger + texto:
  "8 kg disponibles" / "2 kg restantes" / "Agotado").
- Paginación: `Pagination.Root` + `Items` (page_size 50) + `PageText`.
- Vacío total: `EmptyState` con CTA "Cargá tu primer ingrediente".
- Vacío por búsqueda: "Sin resultados para «q»".
- 401 (sesión vencida y refresh falló): `clearSession` + redirect /login
  (comportamiento existente de `api.ts`, sin cambios).

### Form ingrediente (create/edit)
- Campos: Nombre*, Unidad* (Select), Precio por unidad*, Stock inicial
  (solo create), Umbral bajo.
- RHF `register(valueAsNumber)` + `zodResolver`. Errores inline
  (`Field.ErrorText`), a11y nativa de Chakra (aria-invalid, describedby).
- Submit create: POST → `router.push("/admin/ingredients")` + toast.
  409 nombre duplicado → error inline en name ("Ya existe un ingrediente
  con ese nombre").
- Submit edit: PATCH → toast + volver al detalle.
- Cancel: volver (sin perder si hay cambios: confirmar con Dialog).

### Detalle ingrediente (`[id]`)
- Back a listado. Header: nombre + `StockBadge` + precio por unidad.
- `Tabs.Root`: **Resumen** (dl: precio unid., stock actual, umbral,
  unidad) con acciones `Ajustar stock` (primary, abre drawer), `Editar`
  (outline → `[id]/edit`), `Eliminar` (red outline, abre dialog).
- **Movimientos**: `MovementsList` (línea por movimiento: delta firmado
  con color, reason, ref, fecha `formatDateTime`) + paginación si
  `total > 20`.
- `StockDrawer`: delta (NumberInput firmado; helper "Entrada: positivo ·
  Salida: negativo"), reason (Select compra/merma/ajuste), ref (Input
  opcional, "N.º de pedido, ticket…"). Submit → flujo 7.2.

### Importar (RF-P2-07)
- `ImportDialog`: Textarea con helper "Una línea por ingrediente:
  `nombre;unidad;precio`" + botón "Importar".
- Split client de líneas (vacías descartadas, máx 500 — si excede, error
  inline antes del envío).
- Resultado: summary "N creados" + lista de errores por línea (si hay).
- Cierre con success → `reload()` del listado.

### Settings
- Secciones (`Fieldset` + `Legend`): **Horas y margen** (hourly_rate,
  margin_pct) · **Redondeo** (round_step) · **Componentes opcionales**
  (include_labor; include_gas + gas_pct; include_waste + waste_pct) ·
  **Urgencia** (urgent_surcharge_pct) · **Defectos de producto**
  (default_prep_minutes, default_servings, default_difficulty Select).
- Toggles: `Switch` con label descriptivo; el % dependiente queda
  `disabled` y con valor 0 cuando el toggle está off.
- Acciones: ghost "Restaurar valores por defecto" (local) + primary
  "Guardar cambios" (disabled sin cambios; spinner durante PUT).
- 422: errores por campo inline (el detail del backend es una lista;
  mapeo `loc[1] → msg`).

## 9. Accesibilidad
- Labels siempre (`Field.Root`/`Field.Label`); errores ligados
  (`Field.ErrorText` genera `aria-describedby`).
- `StockBadge` lleva texto legible además del color (nunca solo color).
- Tabs de sección = `Tabs.Root` nativo (flechas funcionan).
- Dialog/Drawer: focus trap + `CloseTrigger` + Escape (Chakra v3 lo da).
- Targets ≥44px en mobile; fila de tabla clicable con `role="link"`
  real (usamos `<Link>` dentro de la celda, no onClick).
- `prefers-reduced-motion`: sin animaciones propias en esta fase (Chakra
  respeta el media query en sus transiciones).

## 10. Tests (Vitest + Testing Library)

| Archivo | Cubre |
|---|---|
| `lib/format.test.ts` | money entero/decimal, qty con ceros, signed ±, fecha es-AR |
| `modules/ingredients/schema.test.ts` | create (name vacío, unit fuera de enum, price 0/negativo), update (sin campos → inválido), stock (delta 0 → inválido), import (0 líneas / 501 → inválido) |
| `modules/ingredients/service.test.ts` | URLs/métodos/payload por método; 409 de remove → `ApiError` con `impacted_recipes` |
| `modules/ingredients/components/StockBadge.test.tsx` | los 3 estados (texto + colorPalette) |
| `modules/settings/schema.test.ts` | form completo válido; gas_pct>0 con include_gas off → inválido; waste ídem; margin 101 → inválido; hora 0 → inválido; difficulty fuera de enum |
| `modules/shared/useDebounce.test.tsx` | fake timers: no actualiza antes de 250ms, sí después |

Gates de verificación (todos en `frontend/`):
1. `npx tsc --noEmit` — 0 errores.
2. `npm run lint` — 0 errores.
3. `npx vitest run` — verde.
4. `npm run build` — compila (Next 16, turbopack).
5. Smoke manual si aplica: `npm run dev` + backend local → login admin →
   las 4 rutas nuevas.

## 11. Work units (commits)

| # | Commit | Contenido |
|---|---|---|
| 1 | `chore(frontend): add zod, react-hook-form, vitest + testing-library` | deps + `vitest.config.ts` + `vitest.setup.ts` + script `test` |
| 2 | `feat(frontend): es-AR format utils and typed ApiError` | `lib/format.ts`, `ApiError` en `lib/api.ts`, tests de format |
| 3 | `feat(frontend): admin section layout with nav` | `app/admin/layout.tsx`, `AdminNav`, metadata |
| 4 | `feat(frontend): ingredients list with search, badges, pagination` | types/schema/service/`useIngredients`, `IngredientsPage`, `StockBadge`, `EmptyState`, `useDebounce` + tests |
| 5 | `feat(frontend): ingredient create and edit forms` | `IngredientFormPage` (RHF+zod) + rutas new/[id]/edit + tests de schema |
| 6 | `feat(frontend): ingredient detail, stock drawer, delete, import` | `useIngredientDetail`, `IngredientDetailPage`, `StockDrawer`, `DeleteIngredientDialog`, `ImportDialog`, `MovementsList` + tests de service |
| 7 | `feat(frontend): business settings form` | `settings/*` completo + tests de schema |

Cada commit pasa lint + tsc; tests se commitan con su módulo. PR única
de la fase al terminar los 7 WU.

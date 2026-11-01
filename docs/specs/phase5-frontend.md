# Fase 5 — Productos (frontend)

Módulo: `frontend/src/modules/products` · Rutas: `/productos`, `/productos/[id]`,
`/productos/new`, `/productos/[id]/edit` · Specs: P3 + P4.

Sigue la arquitectura de la Fase 4 (PR #9): `modules/<feature>/{types,schema,service,hooks,components}`,
tipos espejo 1:1 del backend, Money/Qty como string en responses y number en
requests, `apiFetch` + `ApiError`, Chakra v3, react-hook-form + zod.

## Rutas

| Ruta | Guard | Contenido |
|---|---|---|
| `/productos` | sesión (`ProtectedRoute` sin rol) | Vitrina P3: búsqueda, chips de categoría, grilla de cards, paginación 20. |
| `/productos/[id]` | sesión | Detalle P4 en 4 tabs: Información · Ingredientes · Preparación · Costos. |
| `/productos/new` | admin | Wizard de alta (mismo form, `mode="create"`). |
| `/productos/[id]/edit` | admin | Edición (mismo form, `mode="edit"`). |

La lectura está abierta a cualquier usuario autenticado; las mutaciones y el
preview de costos son admin (`require_admin` en el backend).

## Piezas

- `types.ts` — espejo de `backend/src/api/v1/products/schemas.py`.
- `schema.ts` — zod del form (`productFormSchema`): nombre 2..120, categoría
  requerida, receta ≥ 1 línea, `qty > 0`, unidades `kg|g|L|ml|unidad`,
  `prep_time_min > 0`, `.strict()` (el backend usa `extra="forbid"`).
- `service.ts` — `list` / `getDetail` / `create` / `update` / `remove` /
  `preview`. `remove` devuelve `null` (204) o `{impacted_orders}` (200).
- `hooks/useProducts.ts` — lista con debounce 250 ms, filtro de categoría y
  paginación server-side; las categorías vienen del backend en cada respuesta
  (no se derivan de la página).
- `hooks/useProductDetail.ts` — detalle con `reload`.
- `components/ProductsPage.tsx` — P3: chips con `aria-pressed`, grilla 1/2/3
  columnas, skeletons, estado vacío con CTA (solo admin) y "sin resultados".
- `components/ProductCard.tsx` — nombre, categoría, precio (`tabular-nums`) o
  badge "sin precio"; hover solo cambia el outline (RNF-P3-03).
- `components/ProductDetailPage.tsx` — P4: tabs, tabla de receta con costo por
  línea y badge por insumo sin precio, desglose completo y precio por porción.
- `components/ProductFormPage.tsx` — wizard: tabs controladas, errores inline
  por campo, al enviar inválido salta al tab con el primer error.
- `components/RecipeEditor.tsx` — `useFieldArray` de RHF, fila insumo +
  cantidad + unidad + quitar.

## Decisiones

- **Recálculo en vivo** (RF-P4-04): `POST /pricing/preview` con debounce 300 ms
  sobre las líneas válidas. El cliente no reimplementa el motor: así el margen,
  la merma y el redondeo son exactamente los del backend.
- **Borrado** (RF-P4-08): el diálogo advierte que el producto sale del catálogo
  y los pedidos históricos no se tocan; si la API responde `impacted_orders`,
  el toast lo informa. Nunca se bloquea.
- **Draft local** (RNF-P4-02): solo en alta (`product-draft:new` en
  sessionStorage, validado con el schema al restaurar) + `beforeunload` y
  diálogo de confirmación al cancelar con cambios. En edición se carga siempre
  del servidor para no pisar datos vigentes con un borrador viejo.
- **Select nativo de insumos** en lugar de un Combobox: el catálogo de una
  pastelería es chico y el `<select>` es accesible y usable en mobile sin
  código de focus management. Si el catálogo crece, se cambia por
  `@chakra-ui/react` Combobox (el resto del componente no cambia).
- **Insumo sin precio** no bloquea: se advierte en Ingredientes y Costos y el
  producto queda `complete=false` al guardar (RF-P4-07).
- `prep_time_min` con mínimo 1 en el form (RF-P4-06: tiempos > 0); el backend
  acepta 0 porque puede venir del default de settings.

## Gates

- `npx tsc --noEmit` → 0 errores.
- `npm run lint` → 0 errores (2 warnings de `react-hooks/incompatible-library`
  por `watch()` de RHF; uno ya existía en SettingsPage).
- `npm test` → **74 passing** (52 de Fase 4 + 22 nuevos: service, schema y
  componente del listado).
- `npm run build` → OK, 17 rutas (incluye las 4 nuevas).

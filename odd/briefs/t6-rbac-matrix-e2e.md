# Brief T6 — Matriz RBAC + E2E no-fuga de precios

Source de verdad: `odd/tasks/roles-dual-pricing.md` (T6, spec S1).

## Ramas / árbol de trabajo
- Branch actual del repo principal: `test/rbac-matrix-e2e` (base `166ba36`, tip de `feat/roles-frontend` / PR #23).
- Trabajar SIEMPRE en `C:\Users\Usuario\toscana-pastry` (repo principal, sin worktree para esta tarea).
- NO commitear: el orquestador commita y pusha.

## Part A — Matriz RBAC (pytest, backend)

Crear `backend/tests/integration/api/test_rbac_matrix.py` (o extender tests existentes si la matriz ya cubre un caso — verificar primero con CodeGraph; no duplicar).

Matriz (todos contra el endpoint real, sin mocks de auth):

| Rol | Request | Esperado |
|-----|---------|----------|
| `negocio` | `GET /products?audience=consumidor_final` | 403 |
| `negocio` | `GET /products?audience=revendedores` | 200 (precios base) |
| `negocio` | `GET /products/pricelist/csv?audience=consumidor_final` | 403 |
| `negocio` | `GET /products/pricelist/csv?audience=revendedores` | 200 |
| `cliente` | `GET /products?audience=revendedores` | 403 |
| `cliente` | `GET /products?audience=consumidor_final` | 200 (base × (1+markup/100)) |
| `cliente` | `GET /products/pricelist/csv?audience=revendedores` | 403 |
| `cliente` | `GET /products/pricelist/csv?audience=consumidor_final` | 200 |
| `negocio` | `POST /pricing/preview/dual` | 403 |
| `cliente` | `PUT /tenant/settings` | 403 |
| `negocio` | `PUT /tenant/settings` | 403 |
| `admin` | `GET /products?audience=revendedores` y `consumidor_final` | 200 ambos |
| `admin` | `PUT /tenant/settings` (consumer_markup_pct) | 200 |
| `admin` | `GET /products/pricelist/csv` ambas audiencias | 200 |
| anónimo | `GET /products` | 401 |

Verificación de no-fuga (no solo status): en los 200 de `negocio`, la response no debe contener
ningún precio derivado de consumidor final, y viceversa para `cliente`. Comparar contra
`derive_audience_price` (single source of truth, `backend/src/domain/pricing_service.py`).

Patrones a seguir: fixtures de `test_dual_pricing_api.py` / `test_products_listing.py`
(override de `get_db` y `get_current_user`; `async with` en sesiones de repos — ver
descubrimiento del GC leak).

## Part B — E2E Playwright (frontend)

Playwright NO está configurado en el repo (verificar en `frontend/package.json`). Incluir en esta
tarea el setup mínimo:
- `frontend/e2e/` con Playwright Test, config `playwright.config.ts` (webServer que levanta
  `next dev` o build+start; auth fixtures con login real por rol).
- Test `roles-no-leak.spec.ts`: por cada rol (admin/negocio/cliente): login → /products →
  verificar que se ven los productos con el precio de la audiencia propia; verificar que la
  otra audiencia no es visible/selectable en la UI (SegmentGroup); para negocio/cliente:
  intercept `GET /api/v1/products?audience=<otra>` → esperar 403.
- Datos: seed de usuarios por rol y 1 producto con precio base conocido (setup fixture o API
  directa contra el backend de test).
- Si Playwright no puede ejecutarse en el entorno (falta de drivers/crudo de browsers en
  Windows): instalar si es posible; si no, entregar el spec completo + `skip` con motivo
  explícito (mismo patrón que los skips de weasyprint) y reportarlo en el summary.

## Gates
- `python -m pytest -q` desde `backend/`: verde total, 0 regresiones (baseline actual: 324 passed, 5 skipped).
- Frontend: `npx tsc --noEmit`, `npm run lint`, `npm run build`.
- NO agregar vitest (el gate del doc lo menciona pero no hay runner configurado; out of scope salvo que el orquestador lo pida).

## Restricciones
- TDD estricto: RED primero (tests que fallan), luego GREEN. Para la matriz RBAC, si los 403 ya
  existen en el backend, la matriz funcionará como characterization test — documentarlo en el summary.
- Inglés en código, tests y comments.
- No tocar legacy salvo appends. No modificar la lógica de `derive_audience_price`.
- Exploration: CodeGraph siempre, NUNCA grep/rg.
- UI copy en español (idioma de la app).

## Output esperado al terminar
1. Resumen de lo implementado (archivos nuevos/modificados, counts de tests).
2. Resultados de cada gate (pytest, tsc, lint, build, playwright o skip+motivo).
3. Dudas / bloqueantes.
4. NO commitear ni pushar.

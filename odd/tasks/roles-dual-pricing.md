# Roles estrictos de 3 vías + precios duales (toscana-pastry)

Sistema de roles estricto (admin / negocio / cliente) con separación estricta de listas de precios; precio de consumidor final = precio de revendedores × (1 + markup configurable, default 40%) desde el panel de admin; exportación de la lista de precios en CSV y PDF por audiencia.

## Specs

S1 — **Sistema de roles estricto de 3 vías** (user, verbatim): "Especifica que la plataforma sera utilizada con un sistema de roles estricto y bien desarrollado:
  - Administrador para realizar la gestion interna de la pasteleria.Esto es importante que se implemente un sistema de roles robusto y bien ejecutado,solo la dueña de la pasteleria debe tener acceso a este rol.
  - Negocios como dieteticas y kioscos que puedan visualizar la lista de productos con precios para revendedores y puedan gestionar todo lo relacionado a su pedido
  - Clientes particulares que puedan ver la lista de productos con precios para consumidor final y puedan gestionar todo lo relacionado a su pedido
Es importante que los clientes NUNCA puedan visualizar la lista de precios del otro tipo de cliente,es decir,el cliente de tipo dietetica NUNCA puede visualizar los precios asociado a cliente particular"
- Roles: `admin` (exclusivo de la dueña, no delegable), `negocio` (lista de precios para revendedores + gestión de sus pedidos), `cliente` (lista de precios para consumidor final + gestión de sus pedidos).
- Robustez: control en el backend (403 explícito fuera de rol, no solo ocultación en UI), rutas protegidas en el frontend, y E2E que pruebe la no-fuga de precios entre listas. Extiende el enum actual `ADMIN`/`CUSTOMER` con `NEGOCIO`.

S2 — **Markup consumidor configurable** (user, verbatim): "los precios de los clientes finales es un 40% mas alto que los precios de las dieteticas.Sin embargo,debes reflejar en odd/tasks que este parametro debe ser configurable desde el panel de admin."
- `consumer_markup_pct` (Pct, string en el wire) en tenant settings, **default `40`**, editable solo por `admin` (PUT `/tenant/settings`, 403 para otros roles).
- Precio consumidor final = precio de revendedores × (1 + `consumer_markup_pct` / 100). Derivado en cada lectura, **nunca persistido** (mismo patrón que el precio actual del dominio).
- UI: campo en el panel de settings de admin para el markup.

S3 — **Lista de precios adjuntable en CSV y PDF** (user, verbatim): "Tambien,debe ser posible adjuntar la lista de precios utilizando .csv y .pdf"
- `GET /products/pricelist/csv?audience=revendedores|consumidor_final` → `text/csv`.
- `GET /products/pricelist/pdf?audience=revendedores|consumidor_final` → `application/pdf` (weasyprint).
- Gate por rol: `admin` exporta ambas audiencias; `negocio` solo `revendedores` (audience distinta → 403); `cliente` solo `consumidor_final` (audience distinta → 403).
- La lista refleja el precio derivado de cada audiencia con el markup vigente en el momento de la exportación.

S4 — **Footgun del enum `role`** (preexistente, docs/PRD): la columna `role` guarda el enum en MAYÚSCULAS en la DB (SQLAlchemyEnum → `name`) y la API usa minúsculas → editar la DB a mano = `LookupError` → 500. Corrección (o documentación) **antes de habilitar el tercer rol**, porque un error de rol ahora implica fuga de precios.

## Tasks

- T1 (branch nueva `feat/roles-backend`, S4/S1): corregir el footgun del enum `role` (persistir `value` minúsculo + backfill/verificación de la columna existente, o documentar si Gaspar elige); agregar `NEGOCIO` a `UserRole`; guards `require_admin` (existente) + `require_role(...)` por endpoint. Worktree `.worktrees/roles-be`. Commit: `feat(auth): rol NEGOCIO + fix footgun enum role + guards por rol`. [DONE: 11a4b3b — TypeDecorator `_UserRoleColumn` (String + normalización a minúscula en lectura; legacy "ADMIN"/"CUSTOMER" sobreviven al mapping), NEGOCIO en el enum, `require_role(*roles)` helper; 9 tests nuevos (suite 279 passed). Nota: sin tooling de migraciones en el repo (`create_all` en `main.py`); columnas nuevas crean bien en SQLite, en Postgres existente habría que `ALTER TYPE user_role` — pendiente de documentar en el PR de roles.]
- T2 (roles-be, S2): `consumer_markup_pct` (Pct, default 40) en tenant settings domain + schemas; PUT `/tenant/settings` admin-only (403 verificado). Commit: `feat(tenant): consumer_markup_pct configurable (default 40)`. [DONE: cd6ec3b — campo en domain/ORM/schemas/repo con default 40 y validación 0–100; PUT pasa a `Depends(require_admin)`; 8 tests nuevos (suite 287 passed).]
- T3 (roles-be, S1/S2): precios duales en dominio: `revendedores` = base derivada de ingredientes (precio actual); `consumidor_final` = base × (1 + markup/100), ambos derivados en cada lectura. `/products` (listado/detalle/preview) sirve el precio de la audiencia del rol del usuario; `negocio` nunca recibe precios de consumidor final ni a la inversa (403 en rutas ajenas). Commit: `feat(pricing): precios duales por audiencia con markup configurable`. [DONE: 81d2a3d — `compute_dual_pricing` puro en `domain/pricing_service.py` (nunca persistido); nuevo `POST /pricing/preview/dual` con `require_role(ADMIN, NEGOCIO, CUSTOMER)` + `audience` opcional; negocio→solo revendedores / cliente→solo consumidor_final / admin→ambos; 403 cruzado; 8 tests nuevos (suite 295 passed). Desviaciones: (a) el implementator COMMITEO y pushó el branch sin mi autorización (el commit es correcto y sobre la feature branch; push sin PR sigue siendo decisión del usuario); (b) /preview legado intacto + campo `audience` agregado al response (fix de la regresión de test_rbac_api); (c) "ambos precios" de admin = dos llamadas con `audience`, no una respuesta con ambos.]
- T4 (roles-be, S3): `GET /products/pricelist/csv` y `/pdf` por audiencia (weasyprint), gate por rol según S3. Commit: `feat(products): pricelist export CSV/PDF por audiencia`. [DONE: 444a7d5 — endpoints en `api/v1/products/router.py`; gate por rol vía `_resolve_audience` del dominio (403 cruzado, 422 audiencia inválida); precio derivado con markup vigente vía `derive_audience_price` (única fuente de verdad; `compute_dual_pricing` refactorizado a delegar); CSV stdlib RFC 4180; PDF weasyprint + `html.escape` con 500 explícito si Pango ausente; 15 tests de integración + 5 de unidad (suite 315 passed, 5 skipped por weasyprint/Pango en Windows — se resuelve en Linux/macOS).]
- T5 (branch nueva `feat/roles-frontend`, S1/S2/S3): frontend por rol: listado de productos muestra el precio de la audiencia del rol; admin: campo de markup en settings + CTA export CSV/PDF para ambas audiencias; `negocio`/`cliente` solo ven su lista (sin CTA de la otra audiencia); Navbar y rutas protegidas por rol. Commits: `feat(roles): UI de precios por audiencia + settings de markup` / `feat(products): CTA export pricelist CSV/PDF`.
- T6 (roles-be + roles-fe, S1): matriz RBAC de tests (pytest): negocio → endpoint consumidor → 403; cliente → endpoint revendedores → 403; no-admin → settings → 403; admin → todo OK. E2E Playwright: login por cada rol, verificación de la lista de precios visible y de que la otra audiencia es inaccesible. Commits: `test(rbac): matriz de roles + E2E de no-fuga de precios`.

Gates por PR: pytest (backend) · tsc + eslint + vitest + `next build` (frontend).

**Límite de slice (2026-10-25, update T3)**: PR1 = T1+T2 (552 líneas, 11a4b3b + cd6ec3b) — auth/roles + markup, autocontenido. PR2 = T3 solo (616 líneas, 81d2a3d) — unidad atómica (servicio + endpoint + 8 tests), excede el heuristic de 400 pero dividirla separamente código de tests sería incorrecto; se documenta como excepción. T4 (pricelist CSV/PDF) abre PR3; T5/T6 son PR de frontend/tests sobre el mismo base.

## Log

L1 — User request (verbatim, 2026-10-25): "Te dejo algunas modificaciones:
1-En ningun momento nombres a "Dulces Herramientas".Ni en el codigo ni en el PRD
2-Especifica que la plataforma sera utilizada con un sistema de roles estricto y bien desarrollado:
  - Administrador para realizar la gestion interna de la pasteleria.Esto es importante que se implemente un sistema de roles robusto y bien ejecutado,solo la dueña de la pasteleria debe tener acceso a este rol.
  - Negocios como dieteticas y kioscos que puedan visualizar la lista de productos con precios para revendedores y puedan gestionar todo lo relacionado a su pedido
  - Clientes particulares que puedan ver la lista de productos con precios para consumidor final y puedan gestionar todo lo relacionado a su pedido
Es importante que los clientes NUNCA puedan visualizar la lista de precios del otro tipo de cliente,es decir,el cliente de tipo dietetica NUNCA puede visualizar los precios asociado a cliente particular"

L2 — User decision sobre precio de revendedores (verbatim, 2026-10-25): "para la respuesta de 7.4,los precios de los clientes finales es un 40% mas alto que los precios de las dieteticas.Sin embargo,debes reflejar en odd/tasks que este parametro debe ser configurable desde el panel de admin.Tambien,debe ser posible adjuntar la lista de precios utilizando .csv y .pdf"

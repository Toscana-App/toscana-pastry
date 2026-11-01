# Brief C2 — Libro de direcciones por cliente (backend)

Source de verdad: `odd/tasks/checkout-portal-e2e.md` (C2) + `docs/specs/p11_portal_checkout.md` RF-P11-09 + `docs/specs/api_endpoints.md` §FASE 5.

## Árbol de trabajo
- Repo principal `C:\Users\Usuario\toscana-pastry`, branch actual `feat/portal-fase5`.
- Sin worktree. NO commitear ni pushar — el orquestador lo hace.

## Alcance (TDD: RED primero)
Dominio `customer_address` + API por usuario autenticado (`negocio`/`cliente`; `admin` no tiene "mis direcciones" → 403 o 404 según convención del repo):

- `GET /api/v1/customers/me/addresses` → `{items}` (incluye `is_default`)
- `POST /api/v1/customers/me/addresses` `{street_line_1*, street_line_2?, city?, postal_code?, province?, phone?}` → 201 `{address}`
- `PATCH /api/v1/customers/me/addresses/{id}` `{...campos, is_default?}` → 200 / 404
- `DELETE /api/v1/customers/me/addresses/{id}` → 204 / 404 / 409

Reglas (todas testeables):
1. Máx. **5** direcciones por cliente → 6.ª POST = 422.
2. `is_default` exactamente 1: la primera creada pasa a default; `PATCH is_default=true` remueve la anterior (misma transacción).
3. Borrar la default → la primera restante (por `created_at`) pasa a default.
4. Borrar la **única** dirección → 409 (no se deja al cliente sin default).
5. Anti-sondeo: direcciones de otros clientes → 404 (nunca 403 que confirme existencia).

## Convenciones
- Capas: domain (modelo + reglas) · data (repository SQL, `tenant_id` en toda consulta) · api/v1 (router + schemas). Sigue los patrones existentes (ver con CodeGraph el módulo de settings de la calculadora `api/v1/calc/` como referencia de CRUD limpio).
- Pydantic schemas con validación (`street_line_1` requerido, longitud razonable).
- Tests de integración estilo `backend/tests/integration/api/test_calc_support_api.py` (override de `get_db` y `get_user_repository`, SQLite in-memory, `async with` en sesiones).
- Inglés en código/tests/comments. No tocar legacy.

## Gates
- `python -m pytest -q` desde `backend/`: verde total, 0 regresiones (baseline: 340 passed, 5 skipped).
- NO agregues dependencias nuevas.

## Output esperado
1. Resumen: archivos nuevos/modificados, count de tests nuevos.
2. Resultado del gate pytest.
3. Dudas/bloqueantes.
4. Sin commits.

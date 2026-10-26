# Brief C3 — Cupones: dominio + ABM admin (backend)

Source de verdad: `odd/tasks/checkout-portal-e2e.md` (C3) + `docs/specs/p11_portal_checkout.md` RF-P11-14 + `docs/specs/api_endpoints.md` §FASE 5.

## Árbol de trabajo
- Repo principal `C:\Users\Usuario\toscana-pastry`, branch actual `feat/portal-fase5`.
- Sin worktree. NO commitear ni pushar — el orquestador lo hace.

## Alcance (TDD: RED primero)
Dominio `coupon` (monotenante, como el resto de la app) + API **admin-only**:

- `GET /api/v1/coupons` — listado con `?q` (búsqueda case/accent-insensitive en `code`, mismo patrón `accent_fold` que calc), `?status ∈ {active,paused}`, `?page&page_size` (default 50, max 100).
- `POST /api/v1/coupons` — `{code*, type ∈ {percent,fixed}*, value*, valid_from?, valid_until?, max_uses?, status?}` → 201 `{coupon}`.
- `PATCH /api/v1/coupons/{id}` — edita campos / pausa-reactiva (`status`) → 200 / 404.
- `DELETE /api/v1/coupons/{id}` — si está usado en pedidos → 409 (se pausa en su lugar); si no, borra → 204 / 404.

Reglas (todas testeables):
1. `code` único **case-insensitive** → POST duplicado (cualquier case) = 409.
2. `type=percent` → `value` 0–100; `type=fixed` → `value` Money ≥ 0. Inconsistencias = 422.
3. `valid_from`/`valid_until`: si ambas, `valid_until > valid_from` → si no, 422.
4. `max_uses` positiva si presente; `uses` inicia 0 (NO se incrementa en C3 — eso es C4 al confirmar pedido).
5. `status` default `active`; solo `active|paused`.

## Convenciones
- Capas: `domain/coupon.py` (frozen dataclass + validación, estilo `domain/calc_settings.py`) · `data/models.py` (ORM `CouponORM`; **usar estilo `Mapped`/`mapped_column` SA2 como `CustomerAddressORM`**) · `data/repositories/sql_coupon_repository.py` (estilo `sql_calc_supplier_repository.py`) · `api/v1/coupons/` (`router.py` + `schemas.py` + `dependencies.py`, estilo `api/v1/calc/` y `api/v1/customers/`).
- `value` como Money (Decimal, nunca float) — schema estilo `api/v1/money.py`.
- Admin-only: `Depends(require_admin)` en POST/PATCH/DELETE; GET también admin (spec: ABM admin).
- Tests de integración estilo `backend/tests/integration/api/test_calc_support_api.py` (override de `get_db` + `get_user_repository`, SQLite in-memory, `accent_fold` registrada, `async with`).
- Inglés en código/tests; docstrings español (convención del repo). No tocar legacy salvo appends. NO agregues dependencias nuevas.
- C4 (carrito) consumirá `uses`/`max_uses`: deja el repo con métodos limpios (`get_by_code` case-insensitive, `increment_uses`) aunque C3 no los use aún.

## Gates
- `python -m pytest -q` desde `backend/`: verde total, 0 regresiones (baseline actual: 368 passed, 5 skipped).
- NO commitear ni pushar.

## Output esperado
1. Resumen: archivos nuevos/modificados, count de tests nuevos.
2. Resultado del gate pytest.
3. Dudas/bloqueantes.

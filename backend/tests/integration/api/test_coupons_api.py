"""Integration tests for the Coupons admin API (RF-P11-14, C3).

Covers: auth (401/403 admin-only), create (201 + 409 duplicate code
case-insensitive + 422 rules: percent 0-100, fixed >= 0, validity window,
max_uses), list (?q case/accent-insensitive via accent_fold, ?status,
pagination), patch (edit, pause/reactivate, 409 duplicate code, 422
invalid merged state, 404), delete (204 unused, 409 + auto-pause when
used in orders, 404).

Style reference: test_customer_addresses_api.py (C2).
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.coupons.dependencies import get_coupon_repository
from data.accent import accent_fold
from data.db import get_db
from data.models import Base
from data.repositories.sql_coupon_repository import SQLCouponRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app

# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Registrar accent_fold para la búsqueda case/accent-insensitive.
    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_coupon_repo():
        yield SQLCouponRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_coupon_repository] = override_get_coupon_repo

    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )
    await SQLUserRepository(db_session).save(
        User(email="business@example.com", role=UserRole.NEGOCIO)
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


# ─── Helpers ────────────────────────────────────────────────────────────

PATH = "/api/v1/coupons"


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _admin_headers(client: AsyncClient) -> dict:
    return {"Authorization": f"Bearer {await _token_for(client, 'admin@example.com')}"}


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _create(client: AsyncClient, token: str, **fields) -> dict:
    payload = {"code": "VERANO10", "type": "percent", "value": "20", **fields}
    response = await client.post(
        PATH, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["coupon"]


# ─── Auth tests (admin-only) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_requires_auth(client):
    """Sin token → 401."""
    response = await client.get(PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_requires_auth(client):
    """Sin token → 401."""
    response = await client.post(
        PATH, json={"code": "X1", "type": "percent", "value": "10"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_forbidden(client):
    """CUSTOMER no tiene acceso al ABM → 403 en los cuatro verbos."""
    token = await _token_for(client, "customer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get(PATH, headers=headers)).status_code == 403
    assert (
        await client.post(
            PATH,
            json={"code": "X1", "type": "percent", "value": "10"},
            headers=headers,
        )
    ).status_code == 403
    assert (
        await client.patch(f"{PATH}/c1", json={"status": "paused"}, headers=headers)
    ).status_code == 403
    assert (await client.delete(f"{PATH}/c1", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_negocio_forbidden(client):
    """NEGOCIO tampoco (admin-only)."""
    token = await _token_for(client, "business@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(PATH, headers=headers)).status_code == 403


# ─── Create ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_percent_defaults(client):
    """POST percent → 201, uses=0, status=active por defecto, value Money (str)."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="VERANO10", type="percent", value="20")

    # _create usa token; reconstruimos con headers admin reales.
    response = await client.post(
        PATH,
        json={"code": "INVIERNO5", "type": "percent", "value": "5"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()["coupon"]
    assert body["code"] == "INVIERNO5"
    assert body["type"] == "percent"
    assert body["value"] == "5"
    assert body["uses"] == 0
    assert body["status"] == "active"
    assert body["max_uses"] is None
    assert body["valid_from"] is None
    assert body["valid_until"] is None
    assert "id" in body
    assert coupon["code"] == "VERANO10"


@pytest.mark.asyncio
async def test_create_fixed(client):
    """POST fixed con value Money (Decimal, serializado como str)."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "REGALO", "type": "fixed", "value": "5000"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()["coupon"]
    assert body["type"] == "fixed"
    assert body["value"] == "5000"


@pytest.mark.asyncio
async def test_create_decimal_value_roundtrip(client):
    """value decimal (float en JSON) viaja exacto vía Money."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MITAD", "type": "percent", "value": 12.5},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["coupon"]["value"] == "12.5"


@pytest.mark.asyncio
async def test_create_full_payload_roundtrip(client):
    """Todos los campos opcionales se persisten."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={
            "code": "CAFE",
            "type": "fixed",
            "value": "1500.50",
            "valid_from": "2026-10-01T00:00:00Z",
            "valid_until": "2026-12-31T23:59:59Z",
            "max_uses": 25,
            "status": "paused",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()["coupon"]
    assert body["valid_from"] is not None
    assert body["valid_until"] is not None
    assert body["max_uses"] == 25
    assert body["status"] == "paused"
    assert body["value"] == "1500.50"


@pytest.mark.asyncio
async def test_create_duplicate_code_same_case(client):
    """code duplicado mismo case → 409."""
    headers = await _admin_headers(client)
    await client.post(
        PATH, json={"code": "VERANO10", "type": "percent", "value": "10"}, headers=headers
    )
    response = await client.post(
        PATH, json={"code": "VERANO10", "type": "fixed", "value": "5"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_duplicate_code_other_case(client):
    """Unicidad case-insensitive: 'verano10' vs 'VERANO10' → 409."""
    headers = await _admin_headers(client)
    await client.post(
        PATH, json={"code": "VERANO10", "type": "percent", "value": "10"}, headers=headers
    )
    response = await client.post(
        PATH, json={"code": "verano10", "type": "percent", "value": "15"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_percent_over_100_rejected(client):
    """percent con value > 100 → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL1", "type": "percent", "value": "100.01"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_percent_negative_rejected(client):
    """percent con value < 0 → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH, json={"code": "MAL2", "type": "percent", "value": "-1"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_fixed_negative_rejected(client):
    """fixed con value < 0 → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH, json={"code": "MAL3", "type": "fixed", "value": "-0.01"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_type_rejected(client):
    """type fuera de {percent, fixed} → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL4", "type": "second_item", "value": "10"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_status_rejected(client):
    """status fuera de {active, paused} → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL5", "type": "percent", "value": "10", "status": "expired"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_max_uses_zero_rejected(client):
    """max_uses debe ser positiva → 0 es 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL6", "type": "percent", "value": "10", "max_uses": 0},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_valid_until_before_from_rejected(client):
    """valid_until < valid_from → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={
            "code": "MAL7",
            "type": "percent",
            "value": "10",
            "valid_from": "2026-12-01T00:00:00Z",
            "valid_until": "2026-10-01T00:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_valid_until_equal_from_rejected(client):
    """valid_until == valid_from → 422 (debe ser estrictamente mayor)."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={
            "code": "MAL8",
            "type": "percent",
            "value": "10",
            "valid_from": "2026-10-01T00:00:00Z",
            "valid_until": "2026-10-01T00:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_blank_code_rejected(client):
    """code solo espacios → 422."""
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "   ", "type": "percent", "value": "10"},
        headers=headers,
    )
    assert response.status_code == 422


# ─── List ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_empty(client):
    """GET sin cupones → items vacios, total 0."""
    headers = await _admin_headers(client)
    body = (await client.get(PATH, headers=headers)).json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_q_case_insensitive(client):
    """?q busca en code sin distinguir mayusculas."""
    headers = await _admin_headers(client)
    await client.post(
        PATH,
        json={"code": "VERANO10", "type": "percent", "value": "10"},
        headers=headers,
    )
    await client.post(
        PATH,
        json={"code": "OTRO", "type": "percent", "value": "5"},
        headers=headers,
    )

    body = (
        await client.get(PATH, params={"q": "verano"}, headers=headers)
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "VERANO10"


@pytest.mark.asyncio
async def test_list_q_accent_insensitive(client):
    """?q usa el mismo accent_fold que calc: 'cafe' encuentra 'CAFÉ10'."""
    headers = await _admin_headers(client)
    await client.post(
        PATH,
        json={"code": "CAFÉ10", "type": "percent", "value": "10"},
        headers=headers,
    )

    body = (
        await client.get(PATH, params={"q": "cafe10"}, headers=headers)
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "CAFÉ10"


@pytest.mark.asyncio
async def test_list_status_filter(client):
    """?status filtra active/paused."""
    headers = await _admin_headers(client)
    await client.post(
        PATH,
        json={"code": "ACTIVO", "type": "percent", "value": "10"},
        headers=headers,
    )
    await client.post(
        PATH,
        json={"code": "PAUSADO", "type": "percent", "value": "10", "status": "paused"},
        headers=headers,
    )

    active = (
        await client.get(PATH, params={"status": "active"}, headers=headers)
    ).json()
    assert active["total"] == 1
    assert active["items"][0]["code"] == "ACTIVO"

    paused = (
        await client.get(PATH, params={"status": "paused"}, headers=headers)
    ).json()
    assert paused["total"] == 1
    assert paused["items"][0]["code"] == "PAUSADO"


@pytest.mark.asyncio
async def test_list_pagination(client):
    """Paginacion: page_size 2 → 2 items (total 3), page 2 → 1 item."""
    headers = await _admin_headers(client)
    for code in ("AAA", "BBB", "CCC"):
        await client.post(
            PATH,
            json={"code": code, "type": "percent", "value": "10"},
            headers=headers,
        )

    first = (
        await client.get(
            PATH, params={"page": 1, "page_size": 2}, headers=headers
        )
    ).json()
    assert first["total"] == 3
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert len(first["items"]) == 2

    second = (
        await client.get(
            PATH, params={"page": 2, "page_size": 2}, headers=headers
        )
    ).json()
    assert len(second["items"]) == 1


# ─── Patch ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_updates_value(client):
    """PATCH value → 200 con el cupon actualizado."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="EDITAR", type="percent", value="10")

    response = await client.patch(
        f"{PATH}/{coupon['id']}", json={"value": "25"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()["coupon"]
    assert body["value"] == "25"
    assert body["code"] == "EDITAR"


@pytest.mark.asyncio
async def test_patch_pause_and_reactivate(client):
    """PATCH status pausa y reactiva el cupon."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="PAUSA", type="percent", value="10")

    paused = await client.patch(
        f"{PATH}/{coupon['id']}", json={"status": "paused"}, headers=headers
    )
    assert paused.status_code == 200
    assert paused.json()["coupon"]["status"] == "paused"

    reactivated = await client.patch(
        f"{PATH}/{coupon['id']}", json={"status": "active"}, headers=headers
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["coupon"]["status"] == "active"


@pytest.mark.asyncio
async def test_patch_code_change_ok(client):
    """PATCH cambia el code a uno disponible → 200."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="ANTIGUO", type="percent", value="10")

    response = await client.patch(
        f"{PATH}/{coupon['id']}", json={"code": "NUEVO"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["coupon"]["code"] == "NUEVO"


@pytest.mark.asyncio
async def test_patch_code_duplicate_rejected(client):
    """PATCH a un code ya existente (otro case) → 409."""
    headers = await _admin_headers(client)
    await _create(client, await _admin_token(client), code="OCUPADO", type="percent", value="10")
    other = await _create(
        client,
        await _admin_token(client),
        code="LIBRE",
        type="percent",
        value="5",
    )

    response = await client.patch(
        f"{PATH}/{other['id']}", json={"code": "ocupado"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_invalid_percent_rejected(client):
    """PATCH value inválido para percent (estado mergeado) → 422."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="PCT", type="percent", value="10")

    response = await client.patch(
        f"{PATH}/{coupon['id']}", json={"value": "150"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_invalid_validity_window_rejected(client):
    """PATCH que deja valid_until < valid_from → 422."""
    headers = await _admin_headers(client)
    coupon = await _create(
        client,
        await _admin_token(client),
        code="VIG",
        type="percent",
        value="10",
        valid_from="2026-12-01T00:00:00Z",
        valid_until="2026-12-31T00:00:00Z",
    )

    response = await client.patch(
        f"{PATH}/{coupon['id']}",
        json={"valid_until": "2026-11-01T00:00:00Z"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_explicit_null_clears_optional_fields(client):
    """PATCH con null explicito limpia valid_until y max_uses."""
    headers = await _admin_headers(client)
    coupon = await _create(
        client,
        await _admin_token(client),
        code="LIMPIAR",
        type="percent",
        value="10",
        valid_until="2026-12-31T00:00:00Z",
        max_uses=5,
    )

    response = await client.patch(
        f"{PATH}/{coupon['id']}",
        json={"valid_until": None, "max_uses": None},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()["coupon"]
    assert body["valid_until"] is None
    assert body["max_uses"] is None
    assert body["code"] == "LIMPIAR"


@pytest.mark.asyncio
async def test_patch_empty_body_rejected(client):
    """PATCH sin campos → 422."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="VACIO", type="percent", value="10")

    response = await client.patch(f"{PATH}/{coupon['id']}", json={}, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_not_found(client):
    """id inexistente → 404."""
    headers = await _admin_headers(client)
    response = await client.patch(
        f"{PATH}/no-such-id", json={"status": "paused"}, headers=headers
    )
    assert response.status_code == 404


# ─── Delete ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_unused_ok(client):
    """DELETE sin usos → 204 y el cupon desaparece."""
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="BORRAME", type="percent", value="10")

    response = await client.delete(f"{PATH}/{coupon['id']}", headers=headers)
    assert response.status_code == 204

    body = (await client.get(PATH, headers=headers)).json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_delete_used_returns_409_and_pauses(client, db_session):
    """DELETE usado en pedidos → 409; el cupon se pausa (no se borra).

    En C3 no hay tabla de pedidos: se simula el uso con increment_uses
    (el mismo metodo que consumira C4 al confirmar un pedido).
    """
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="USADO", type="percent", value="10")

    repo = SQLCouponRepository(db_session)
    used = await repo.increment_uses(coupon["id"])
    assert used is not None and used.uses == 1

    response = await client.delete(f"{PATH}/{coupon['id']}", headers=headers)
    assert response.status_code == 409

    body = (await client.get(PATH, headers=headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "USADO"
    assert body["items"][0]["status"] == "paused"


@pytest.mark.asyncio
async def test_delete_not_found(client):
    """id inexistente → 404."""
    headers = await _admin_headers(client)
    response = await client.delete(f"{PATH}/no-such-id", headers=headers)
    assert response.status_code == 404


# ─── code_key UNIQUE (race-safe duplicate detection) ────────────────────


@pytest.mark.asyncio
async def test_create_duplicate_code_accent_and_case(client):
    """'CAFE10' vs 'café10' differ only by case/accent -> 409."""
    headers = await _admin_headers(client)
    await _create(client, await _admin_token(client), code="CAFE10")
    response = await client.post(
        PATH, json={"code": "café10", "type": "percent", "value": "5"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_race_hits_db_constraint_returns_409(client, monkeypatch):
    """Concurrent-style: the app pre-check misses (both requests read before
    either commits), so the DB UNIQUE on code_key must produce the 409."""
    headers = await _admin_headers(client)
    await _create(client, await _admin_token(client), code="CAFE10")

    async def _miss(self, code):
        return None

    monkeypatch.setattr(SQLCouponRepository, "get_by_code", _miss)
    response = await client.post(
        PATH, json={"code": "Café10", "type": "percent", "value": "5"}, headers=headers
    )
    assert response.status_code == 409
    assert "Café10" in response.json()["detail"]


@pytest.mark.asyncio
async def test_patch_race_hits_db_constraint_returns_409(client, monkeypatch):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _create(client, token, code="CAFE10")
    other = await _create(client, token, code="OTRO")

    async def _miss(self, code):
        return None

    monkeypatch.setattr(SQLCouponRepository, "get_by_code", _miss)
    response = await client.patch(
        f"{PATH}/{other['id']}", json={"code": "café10"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_db_rejects_duplicate_code_key(db_session):
    """DB level: two rows with the same code_key raise IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    from data.models import CouponORM

    def _row(i, code):
        return CouponORM(
            id=f"id-{i}", code=code, code_key=accent_fold(code),
            type="percent", value="10",
        )

    db_session.add(_row(1, "CAFE10"))
    await db_session.commit()
    db_session.add(_row(2, "café10"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

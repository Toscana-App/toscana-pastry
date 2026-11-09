
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.coupons.dependencies import get_coupon_repository
from data.accent import accent_fold
from data.db import get_db
from data.repositories.sql_coupon_repository import SQLCouponRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app


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



PATH = "/api/v1/coupons"


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.cookies["auth_token"]


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



@pytest.mark.asyncio
async def test_list_requires_auth(client):
    response = await client.get(PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_requires_auth(client):
    response = await client.post(
        PATH, json={"code": "X1", "type": "percent", "value": "10"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_customer_forbidden(client):
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
    token = await _token_for(client, "business@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(PATH, headers=headers)).status_code == 403



@pytest.mark.asyncio
async def test_create_percent_defaults(client):
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="VERANO10", type="percent", value="20")

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
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL1", "type": "percent", "value": "100.01"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_percent_negative_rejected(client):
    headers = await _admin_headers(client)
    response = await client.post(
        PATH, json={"code": "MAL2", "type": "percent", "value": "-1"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_fixed_negative_rejected(client):
    headers = await _admin_headers(client)
    response = await client.post(
        PATH, json={"code": "MAL3", "type": "fixed", "value": "-0.01"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_type_rejected(client):
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL4", "type": "second_item", "value": "10"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_status_rejected(client):
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL5", "type": "percent", "value": "10", "status": "expired"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_max_uses_zero_rejected(client):
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "MAL6", "type": "percent", "value": "10", "max_uses": 0},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_valid_until_before_from_rejected(client):
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
    headers = await _admin_headers(client)
    response = await client.post(
        PATH,
        json={"code": "   ", "type": "percent", "value": "10"},
        headers=headers,
    )
    assert response.status_code == 422



@pytest.mark.asyncio
async def test_list_empty(client):
    headers = await _admin_headers(client)
    body = (await client.get(PATH, headers=headers)).json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_q_case_insensitive(client):
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



@pytest.mark.asyncio
async def test_patch_updates_value(client):
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
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="ANTIGUO", type="percent", value="10")

    response = await client.patch(
        f"{PATH}/{coupon['id']}", json={"code": "NUEVO"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["coupon"]["code"] == "NUEVO"


@pytest.mark.asyncio
async def test_patch_code_duplicate_rejected(client):
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
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="PCT", type="percent", value="10")

    response = await client.patch(
        f"{PATH}/{coupon['id']}", json={"value": "150"}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_invalid_validity_window_rejected(client):
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
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="VACIO", type="percent", value="10")

    response = await client.patch(f"{PATH}/{coupon['id']}", json={}, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_not_found(client):
    headers = await _admin_headers(client)
    response = await client.patch(
        f"{PATH}/no-such-id", json={"status": "paused"}, headers=headers
    )
    assert response.status_code == 404



@pytest.mark.asyncio
async def test_delete_unused_ok(client):
    headers = await _admin_headers(client)
    coupon = await _create(client, await _admin_token(client), code="BORRAME", type="percent", value="10")

    response = await client.delete(f"{PATH}/{coupon['id']}", headers=headers)
    assert response.status_code == 204

    body = (await client.get(PATH, headers=headers)).json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_delete_used_returns_409_and_pauses(client, db_session):
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
    headers = await _admin_headers(client)
    response = await client.delete(f"{PATH}/no-such-id", headers=headers)
    assert response.status_code == 404




@pytest.mark.asyncio
async def test_create_duplicate_code_accent_and_case(client):
    headers = await _admin_headers(client)
    await _create(client, await _admin_token(client), code="CAFE10")
    response = await client.post(
        PATH, json={"code": "café10", "type": "percent", "value": "5"}, headers=headers
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_race_hits_db_constraint_returns_409(client, monkeypatch):
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

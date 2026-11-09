import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole

SETTINGS_PATH = "/api/v1/tenant/settings"


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


def _valid_payload(**overrides) -> dict:
    payload = {
        "hourly_rate": 300000,
        "margin_pct": "50",
        "round_step": 10000,
        "include_labor": True,
        "include_gas": True,
        "gas_pct": "3",
        "include_waste": True,
        "waste_pct": "3",
        "urgent_surcharge_pct": "20",
        "default_prep_minutes": 30,
        "default_servings": 6,
        "default_difficulty": "simple",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_get_settings_requires_authentication(client):
    response = await client.get(SETTINGS_PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_returns_system_defaults_when_unset(client):
    token = await _admin_token(client)
    response = await client.get(
        SETTINGS_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hourly_rate"] == 300000
    assert Decimal(body["margin_pct"]) == Decimal("30")
    assert body["round_step"] == 10000
    assert body["include_labor"] is True
    assert body["include_gas"] is True
    assert Decimal(body["gas_pct"]) == Decimal("3")
    assert body["include_waste"] is True
    assert Decimal(body["waste_pct"]) == Decimal("3")
    assert Decimal(body["urgent_surcharge_pct"]) == Decimal("20")


@pytest.mark.asyncio
async def test_get_settings_forbidden_for_customer(client):
    token = await _customer_token(client)
    response = await client.get(
        SETTINGS_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_put_settings_forbidden_for_customer(client):
    token = await _customer_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_put_settings_updates_and_persists(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(SETTINGS_PATH, json=_valid_payload(), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["margin_pct"]) == Decimal("50")
    assert body["include_gas"] is True
    assert Decimal(body["gas_pct"]) == Decimal("3")

    reread = await client.get(SETTINGS_PATH, headers=headers)
    assert reread.json() == body


@pytest.mark.asyncio
async def test_put_settings_persists_urgent_surcharge(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(urgent_surcharge_pct="35"),
        headers=headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["urgent_surcharge_pct"]) == Decimal("35")

    reread = await client.get(SETTINGS_PATH, headers=headers)
    assert Decimal(reread.json()["urgent_surcharge_pct"]) == Decimal("35")


@pytest.mark.asyncio
async def test_put_settings_accepts_numbers_not_only_strings(client):
    token = await _admin_token(client)
    payload = _valid_payload()
    payload["hourly_rate"] = 3200
    payload["margin_pct"] = 55.5
    response = await client.put(
        SETTINGS_PATH, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert Decimal(response.json()["margin_pct"]) == Decimal("55.5")


@pytest.mark.asyncio
async def test_put_settings_accepts_margin_edges(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    for margin in ("0", "100"):
        response = await client.put(
            SETTINGS_PATH, json=_valid_payload(margin_pct=margin), headers=headers
        )
        assert response.status_code == 200
        assert Decimal(response.json()["margin_pct"]) == Decimal(margin)


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_below_range(client):
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(margin_pct="-1"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "margin_pct" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_above_range(client):
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(margin_pct="101"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "margin_pct" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_percent_with_toggle_off(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    gas = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(include_gas=False, gas_pct="10"),
        headers=headers,
    )
    assert gas.status_code == 422
    assert "gas_pct" in str(gas.json())

    waste = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(include_waste=False, waste_pct="10"),
        headers=headers,
    )
    assert waste.status_code == 422
    assert "waste_pct" in str(waste.json())


@pytest.mark.asyncio
async def test_put_settings_accepts_toggle_off_with_zero_percent(client):
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(include_gas=False, gas_pct="0"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["include_gas"] is False


@pytest.mark.asyncio
async def test_put_settings_rejects_zero_round_step(client):
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(round_step=0),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_rejects_unknown_field(client):
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(discount_pct="5"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

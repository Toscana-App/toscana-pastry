import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole


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


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _set_settings(client: AsyncClient, headers) -> None:
    response = await client.put(
        "/api/v1/tenant/settings",
        json={
            "hourly_rate": 15000,
            "margin_pct": "100",
            "round_step": 500,
            "include_labor": True,
            "include_gas": False,
            "gas_pct": "0",
            "include_waste": False,
            "waste_pct": "0",
            "urgent_surcharge_pct": "20",
            "default_prep_minutes": 30,
            "default_servings": 6,
            "default_difficulty": "simple",
        },
        headers=headers,
    )
    assert response.status_code == 200


TORTA_ITEMS = [
    {"qty": "250", "unit": "g", "price_per_purchase_unit": 280000, "purchase_unit": "kg"},
    {"qty": "4", "unit": "unidad", "price_per_purchase_unit": 9000, "purchase_unit": "unidad"},
    {"qty": "1.5", "unit": "l", "price_per_purchase_unit": 120000, "purchase_unit": "l"},
]


@pytest.mark.asyncio
async def test_preview_requires_authentication(client):
    response = await client.post(
        "/api/v1/pricing/preview",
        json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preview_uses_persisted_settings(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    await _set_settings(client, headers)

    response = await client.post(
        "/api/v1/pricing/preview",
        json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["materials"] == 286000
    assert body["labor"] == 7500
    assert body["base"] == 293500
    assert body["final"] == 587000
    assert body["rounded"] == 587000


@pytest.mark.asyncio
async def test_preview_forbidden_for_customer(client):
    login = await client.post(
        "/api/v1/auth/login", json={"email": "customer@example.com"}
    )
    token = login.cookies["auth_token"]
    response = await client.post(
        "/api/v1/pricing/preview",
        json={"line_items": TORTA_ITEMS, "prep_minutes": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_preview_incompatible_units_returns_400(client):
    token = await _admin_token(client)
    response = await client.post(
        "/api/v1/pricing/preview",
        json={
            "line_items": [
                {"qty": "100", "unit": "g", "price_per_purchase_unit": 9000, "purchase_unit": "unidad"},
            ],
            "prep_minutes": 30,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_preview_rejects_empty_line_items(client):
    token = await _admin_token(client)
    response = await client.post(
        "/api/v1/pricing/preview",
        json={"line_items": [], "prep_minutes": 30},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_preview_rejects_negative_minutes(client):
    token = await _admin_token(client)
    response = await client.post(
        "/api/v1/pricing/preview",
        json={"line_items": TORTA_ITEMS, "prep_minutes": -5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

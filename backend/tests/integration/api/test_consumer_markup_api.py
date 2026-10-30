"""Tests for consumer_markup_pct on tenant settings (S2)."""

import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from main import app
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole

SETTINGS_PATH = "/api/v1/tenant/settings"


@pytest_asyncio.fixture
async def admin_client(db_session):
    """Client with admin user pre-seeded."""
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


@pytest_asyncio.fixture
async def customer_client(db_session):
    """Client with customer user pre-seeded."""
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


@pytest_asyncio.fixture
async def negocio_client(db_session):
    """Client with negocio user pre-seeded."""
    await SQLUserRepository(db_session).save(
        User(email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
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
    return response.json()["access_token"]


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


async def _negocio_token(client: AsyncClient) -> str:
    return await _token_for(client, "negocio@example.com")


_BASE_PAYLOAD = {
    "hourly_rate": "3000",
    "margin_pct": "30",
    "round_step": "100",
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


# ---- S2: PUT consumer_markup_pct persists and round-trips ----


@pytest.mark.asyncio
async def test_put_consumer_markup_persists_and_rereads(admin_client):
    """S2: PUT consumer_markup_pct='25' persists; GET returns it."""
    token = await _admin_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}

    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="25")
    response = await admin_client.put(
        SETTINGS_PATH, json=payload, headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["consumer_markup_pct"]) == Decimal("25")

    reread = await admin_client.get(SETTINGS_PATH, headers=headers)
    assert Decimal(reread.json()["consumer_markup_pct"]) == Decimal("25")


@pytest.mark.asyncio
async def test_get_consumer_markup_default_is_40(admin_client):
    """S2: consumer_markup_pct defaults to 40 when not set."""
    token = await _admin_token(admin_client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await admin_client.get(SETTINGS_PATH, headers=headers)
    assert response.status_code == 200
    assert Decimal(response.json()["consumer_markup_pct"]) == Decimal("40")


# ---- S2: admin-only guard (PUT forbidden for non-admin) ----


@pytest.mark.asyncio
async def test_put_consumer_markup_forbidden_for_customer(customer_client):
    """S2: customer cannot PUT settings → 403."""
    token = await _customer_token(customer_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="50")
    response = await customer_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_put_consumer_markup_forbidden_for_negocio(negocio_client):
    """S2: negocio cannot PUT settings → 403."""
    token = await _negocio_token(negocio_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="50")
    response = await negocio_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---- S2: range validation (0-100) ----


@pytest.mark.asyncio
async def test_put_consumer_markup_rejects_above_100(admin_client):
    """S2: consumer_markup_pct=101 → 422."""
    token = await _admin_token(admin_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="101")
    response = await admin_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "consumer_markup_pct" in str(response.json())


@pytest.mark.asyncio
async def test_put_consumer_markup_rejects_negative(admin_client):
    """S2: consumer_markup_pct=-1 → 422."""
    token = await _admin_token(admin_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="-1")
    response = await admin_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "consumer_markup_pct" in str(response.json())


@pytest.mark.asyncio
async def test_put_consumer_markup_accepts_zero(admin_client):
    """S2: consumer_markup_pct=0 is valid (edge)."""
    token = await _admin_token(admin_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="0")
    response = await admin_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert Decimal(response.json()["consumer_markup_pct"]) == Decimal("0")


@pytest.mark.asyncio
async def test_put_consumer_markup_accepts_100(admin_client):
    """S2: consumer_markup_pct=100 is valid (edge)."""
    token = await _admin_token(admin_client)
    payload = dict(_BASE_PAYLOAD, consumer_markup_pct="100")
    response = await admin_client.put(
        SETTINGS_PATH, json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert Decimal(response.json()["consumer_markup_pct"]) == Decimal("100")

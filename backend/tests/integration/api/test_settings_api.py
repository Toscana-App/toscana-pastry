import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


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


def _valid_payload(**overrides) -> dict:
    payload = {
        "hourly_rate": "150",
        "margin_pct": "150",
        "round_step": "5",
        "include_labor": True,
        "include_gas": True,
        "gas_pct": "10",
        "include_waste": False,
        "waste_pct": "0",
        "default_prep_minutes": 30,
        "default_servings": 6,
        "default_difficulty": "simple",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_get_settings_requires_authentication(client):
    response = await client.get("/api/v1/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_returns_defaults_when_unset(client):
    token = await _token_for(client, "admin@example.com")
    response = await client.get(
        "/api/v1/settings", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["include_labor"] is True
    assert body["include_gas"] is False
    assert body["include_waste"] is False
    assert Decimal(body["round_step"]) > 0
    assert Decimal(body["hourly_rate"]) > 0
    assert Decimal(body["margin_pct"]) > 0


@pytest.mark.asyncio
async def test_get_settings_allowed_for_any_authenticated_user(client, db_session):
    # La spec exige usuario autenticado (401), no un rol específico.
    await SQLUserRepository(db_session).save(User(email="customer@example.com"))
    token = await _token_for(client, "customer@example.com")
    response = await client.get(
        "/api/v1/settings", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_put_settings_updates_and_persists(client):
    token = await _token_for(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put("/api/v1/settings", json=_valid_payload(), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["margin_pct"]) == Decimal("150")
    assert body["include_gas"] is True
    assert Decimal(body["gas_pct"]) == Decimal("10")

    reread = await client.get("/api/v1/settings", headers=headers)
    assert reread.json() == body


@pytest.mark.asyncio
async def test_put_settings_accepts_numbers_not_only_strings(client):
    token = await _token_for(client, "admin@example.com")
    payload = _valid_payload()
    payload["hourly_rate"] = 200
    payload["margin_pct"] = 120.5
    response = await client.put(
        "/api/v1/settings", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert Decimal(response.json()["margin_pct"]) == Decimal("120.5")


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_below_range(client):
    # El rango se valida en el schema (ge/le de Field): 422 con detalle.
    # El 400 del dominio es segunda linea para quien construya BusinessSettings
    # programaticamente (cubierto en los tests unitarios).
    token = await _token_for(client, "admin@example.com")
    response = await client.put(
        "/api/v1/settings",
        json=_valid_payload(margin_pct="9"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "margin_pct" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_above_range(client):
    token = await _token_for(client, "admin@example.com")
    response = await client.put(
        "/api/v1/settings",
        json=_valid_payload(margin_pct="201"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_rejects_zero_round_step(client):
    token = await _token_for(client, "admin@example.com")
    response = await client.put(
        "/api/v1/settings",
        json=_valid_payload(round_step="0"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_rejects_unknown_field(client):
    token = await _token_for(client, "admin@example.com")
    response = await client.put(
        "/api/v1/settings",
        json=_valid_payload(discount_pct="5"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

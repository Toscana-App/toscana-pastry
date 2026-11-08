"""Integration tests for the Calc Settings API (GET/PUT /api/v1/calc/settings).

Cubre auth (401/403), defaults, persistencia, validacion de rangos y
extra="forbid" (S1, S3).
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.dependencies import get_user_repository
from api.v1.calc.dependencies import get_calc_settings_repository
from data.repositories.calc.sql_calc_settings_repository import SQLCalcSettingsRepository
from data.db import get_db
from domain.models import User, UserRole

SETTINGS_PATH = "/api/v1/calc/settings"


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_calc_settings_repository():
        yield SQLCalcSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_calc_settings_repository] = override_get_calc_settings_repository

    # El login crea usuarios con rol CUSTOMER: se siembra ADMIN antes de las requests.
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


# ─── Helpers ────────────────────────────────────────────────────────────

async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


def _valid_payload(**overrides) -> dict:
    payload = {
        "business_name": "Mi Panaderia",
        "main_currency_name": "Peso",
        "main_currency_symbol": "$",
        "default_margin_percent": "30",
        "default_discount_percent": "0",
        "default_tax_percent": "19",
        "rounding_mode": "none",
    }
    payload.update(overrides)
    return payload


# ─── Auth tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_settings_requires_authentication(client):
    """S3: sin sesion → 401."""
    response = await client.get(SETTINGS_PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_settings_requires_authentication(client):
    """S3: sin sesion → 401."""
    response = await client.put(SETTINGS_PATH, json=_valid_payload())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_settings_forbidden_for_customer(client):
    """S3: no-admin → 403 en PUT."""
    token = await _customer_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ─── GET tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_settings_returns_system_defaults_when_unset(client):
    """S1: GET devuelve defaults del sistema cuando no hay fila."""
    token = await _admin_token(client)
    response = await client.get(
        SETTINGS_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Mi Negocio"
    assert body["main_currency_name"] == "Peso"
    assert body["main_currency_symbol"] == "$"
    assert Decimal(body["default_margin_percent"]) == Decimal("30")
    assert Decimal(body["default_discount_percent"]) == Decimal("0")
    assert Decimal(body["default_tax_percent"]) == Decimal("19")
    assert body["rounding_mode"] == "none"


@pytest.mark.asyncio
async def test_get_settings_forbidden_for_customer(client):
    token = await _customer_token(client)
    response = await client.get(
        SETTINGS_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


# ─── PUT tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_put_settings_updates_and_persists(client):
    """S1: PUT actualiza y persiste."""
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        SETTINGS_PATH, json=_valid_payload(), headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["business_name"] == "Mi Panaderia"
    assert Decimal(body["default_margin_percent"]) == Decimal("30")

    # Releer: persiste
    reread = await client.get(SETTINGS_PATH, headers=headers)
    assert reread.json() == body


@pytest.mark.asyncio
async def test_put_settings_accepts_decimal_numbers(client):
    """PUT acepta numeros (no solo strings)."""
    token = await _admin_token(client)
    payload = _valid_payload()
    payload["default_margin_percent"] = str(Decimal("45.5"))
    response = await client.put(
        SETTINGS_PATH, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert Decimal(response.json()["default_margin_percent"]) == Decimal("45.5")


@pytest.mark.asyncio
async def test_put_settings_accepts_margin_edges(client):
    """S1: margen 0 y 100 son validos."""
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    for margin in ("0", "100"):
        response = await client.put(
            SETTINGS_PATH,
            json=_valid_payload(default_margin_percent=margin),
            headers=headers,
        )
        assert response.status_code == 200
        assert Decimal(response.json()["default_margin_percent"]) == Decimal(margin)


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_below_range(client):
    """S1: margen -1 → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(default_margin_percent="-1"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "default_margin_percent" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_margin_above_range(client):
    """S1: margen 101 → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(default_margin_percent="101"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_rejects_discount_below_range(client):
    """S1: descuento -1 → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(default_discount_percent="-1"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "default_discount_percent" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_tax_above_range(client):
    """S1: impuesto 101 → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(default_tax_percent="101"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "default_tax_percent" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_rejects_invalid_rounding_mode(client):
    """S1: rounding_mode invalido → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(rounding_mode="invalid"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "rounding_mode" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_accepts_all_rounding_modes(client):
    """S1: todos los modos de redondeo son validos."""
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    for mode in ("none", "integer", "multiple_10", "commercial_99"):
        response = await client.put(
            SETTINGS_PATH,
            json=_valid_payload(rounding_mode=mode),
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["rounding_mode"] == mode


@pytest.mark.asyncio
async def test_put_settings_rejects_unknown_field(client):
    """S1: extra="forbid" rechaza campos desconocidos → 422."""
    token = await _admin_token(client)
    payload = _valid_payload()
    payload["unknown_field"] = "test"
    response = await client.put(
        SETTINGS_PATH, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_business_name_min_length(client):
    """S1: business_name vacio → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(business_name=""),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "business_name" in str(response.json())


@pytest.mark.asyncio
async def test_put_settings_currency_symbol_min_length(client):
    """S1: main_currency_symbol vacio → 422."""
    token = await _admin_token(client)
    response = await client.put(
        SETTINGS_PATH,
        json=_valid_payload(main_currency_symbol=""),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "main_currency_symbol" in str(response.json())

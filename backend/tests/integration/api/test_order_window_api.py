"""Ventana de pedidos / corte de pedidos (RF-P5-07 y RF-P6-09): API.

Fixture por test: sesión SQLite en memoria con los overrides de la
suite. Sin configuración previa la ventana existe por defecto abierta.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.order_window.router import get_order_repository
from domain.models import User, UserRole

WINDOW_PATH = "/api/v1/tenant/order-window"


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
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
    return response.json()["access_token"]


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


@pytest.mark.asyncio
async def test_get_order_window_requires_authentication(client):
    response = await client.get(WINDOW_PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_order_window_forbidden_for_customer(client):
    token = await _customer_token(client)
    response = await client.get(
        WINDOW_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_get_order_window_returns_default_open(client):
    # RF-P6-09: sin configuración previa la ventana existe por defecto
    # abierta, sin fecha de reapertura y sin mensaje.
    token = await _admin_token(client)
    response = await client.get(
        WINDOW_PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["open"] is True
    assert body["reopens_at"] is None
    assert body["message"] == ""


@pytest.mark.asyncio
async def test_patch_order_window_closes_with_reopens_at(client):
    # RF-P5-07: cerrar con reopens_at → 200 y el estado persiste.
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    reopens = "2026-11-08T20:00:00"

    response = await client.patch(
        WINDOW_PATH,
        json={"open": False, "reopens_at": reopens, "message": "Cerrado por mantenimiento"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["open"] is False
    assert body["reopens_at"] == reopens
    assert body["message"] == "Cerrado por mantenimiento"

    reread = await client.get(WINDOW_PATH, headers=headers)
    assert reread.json() == body


@pytest.mark.asyncio
async def test_patch_order_window_close_without_reopens_at_422(client):
    # Cerrar sin reopens_at → 422 con mensaje de sugerencia.
    token = await _admin_token(client)
    response = await client.patch(
        WINDOW_PATH,
        json={"open": False, "message": "Cerrado"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "reopens_at" in response.json()["detail"]


@pytest.mark.asyncio
async def test_patch_order_window_message_too_long_422(client):
    # message > 200 caracteres → 422 (validación del schema).
    token = await _admin_token(client)
    response = await client.patch(
        WINDOW_PATH,
        json={
            "open": False,
            "reopens_at": "2026-11-08T20:00:00",
            "message": "x" * 201,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_order_window_open_forces_reopens_at_null(client):
    # open=true → reopens_at siempre nulo, aunque el payload la traiga.
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Primero cerrar (para tener un reopens_at previo que limpiar).
    closed = await client.patch(
        WINDOW_PATH,
        json={"open": False, "reopens_at": "2026-11-08T20:00:00", "message": ""},
        headers=headers,
    )
    assert closed.status_code == 200
    assert closed.json()["reopens_at"] == "2026-11-08T20:00:00"

    response = await client.patch(
        WINDOW_PATH,
        json={"open": True, "reopens_at": "2026-11-08T20:00:00", "message": ""},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["open"] is True
    assert response.json()["reopens_at"] is None


@pytest.mark.asyncio
async def test_patch_order_window_requires_open_field(client):
    # `open` es requerido en el body: sin él → 422.
    token = await _admin_token(client)
    response = await client.patch(
        WINDOW_PATH,
        json={"message": "sin open"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_order_window_forbidden_for_customer(client):
    token = await _customer_token(client)
    response = await client.patch(
        WINDOW_PATH,
        json={"open": False, "reopens_at": "2026-11-08T20:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

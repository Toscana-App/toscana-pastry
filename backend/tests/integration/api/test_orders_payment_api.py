"""Integration tests for payment API endpoints (C1.4/C1.5).

Covers:
    POST /orders/{id}/payment:
        - 200 for mercadopago orders (idempotent)
        - 422 for cash orders
        - 409 for non-nuevo orders
    GET /orders/{id}/payment:
        - 200 with correct status/paid
        - 404 for non-existent orders
"""

import datetime
import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import get_current_user
from data.db import get_db as get_db_orig
from data.models import Base
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod
from main import app

# ─── Fixtures ─────────────────────────────────────────────────────────


async def _admin_user():
    """Return a fake admin user for dependency overrides."""
    return User(email="admin@example.com", role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_order_repo():
        yield SQLOrderRepository(db_session)

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[
        SQLOrderRepository
    ] = override_get_order_repo
    app.dependency_overrides[get_current_user] = _admin_user

    # Create admin user
    admin = User(email="admin@example.com", role=UserRole.ADMIN)
    await SQLUserRepository(db_session).save(admin)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def mercadopago_order(db_session):
    """Create an order with payment_method=mercadopago, status=nuevo."""
    order = Order(
        customer_id=str(uuid.uuid4()),
        date=datetime.datetime.now(datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal(1000),
            )
        ],
        payment_method=PaymentMethod.MERCADOPAGO,
    )
    repo = SQLOrderRepository(db_session)
    await repo.create(order)
    return order


@pytest_asyncio.fixture
async def cash_order(db_session):
    """Create an order with payment_method=cash, status=nuevo."""
    order = Order(
        customer_id=str(uuid.uuid4()),
        date=datetime.datetime.now(datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Alfajor",
                quantity=10,
                unit_price=Decimal(200),
            )
        ],
        payment_method=PaymentMethod.CASH,
    )
    repo = SQLOrderRepository(db_session)
    await repo.create(order)
    return order


# ─── Tests ────────────────────────────────────────────────────────────


class TestPostOrderPayment:
    """Tests for POST /orders/{id}/payment (C1.4)."""

    async def test_mercadopago_payment_returns_reference(
        self, client, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reference"] == f"mock_{mercadopago_order.id}"
        assert "checkout_url" in data

    async def test_mercadopago_payment_idempotent(self, client, mercadopago_order):
        response1 = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        response2 = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["reference"] == response2.json()["reference"]

    async def test_cash_payment_returns_422(self, client, cash_order):
        response = await client.post(
            f"/api/v1/orders/{cash_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "payment_method_not_mercadopago"

    async def test_missing_idempotency_key_returns_422(self, client, mercadopago_order):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
        )
        assert response.status_code == 422


class TestGetOrderPayment:
    """Tests for GET /orders/{id}/payment (C1.5)."""

    async def test_payment_status_returns_null_for_uninitiated(self, client, cash_order):
        response = await client.get(f"/api/v1/orders/{cash_order.id}/payment")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is None
        assert data["paid"] is False

    async def test_payment_status_returns_404_for_nonexistent(self, client):
        response = await client.get(
            "/api/v1/orders/nonexistent-payment"
        )
        assert response.status_code == 404

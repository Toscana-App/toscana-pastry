"""Integration tests: owner access to payment endpoints (F3, RF-P11-10).

El polling del portal (GET /orders/{id}/payment) y el init (POST) deben
ser accesibles por el PROPIETARIO del pedido, no solo por admin.
Pedidos ajenos → 404 (anti-sondeo).
"""

import datetime
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
from api.v1.orders.dependencies import get_checkout_provider
from data.db import get_db as get_db_orig
from data.models import Base
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.checkout_provider import PaymentResult
from domain.order import Order, OrderItem, PaymentMethod
from main import app


@pytest_asyncio.fixture
async def owner(db_session):
    user = User(email="owner@example.com", role=UserRole.CUSTOMER)
    await SQLUserRepository(db_session).save(user)
    return user


@pytest_asyncio.fixture
async def stranger(db_session):
    user = User(email="stranger@example.com", role=UserRole.CUSTOMER)
    await SQLUserRepository(db_session).save(user)
    return user


class _FakeProvider:
    """In-memory provider: no network, deterministic reference."""

    async def create_payment(self, order_id, amount, currency):
        return PaymentResult(
            reference=f"mock_{order_id}", checkout_url=f"https://pay.test/{order_id}"
        )


def _client_for(user: User, db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_order_repo():
        yield SQLOrderRepository(db_session)

    async def override_current_user():
        return user

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[SQLOrderRepository] = override_get_order_repo
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_checkout_provider] = lambda: _FakeProvider()
    return override_current_user


def _make_order(customer_id: str) -> Order:
    return Order(
        customer_id=customer_id,
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


class TestGetPaymentOwner:
    async def test_owner_can_poll_own_order(self, db_session, owner):
        order = _make_order(owner.id)
        await SQLOrderRepository(db_session).create(order)
        _client_for(owner, db_session)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ax:
                res = await ax.get(f"/api/v1/orders/{order.id}/payment")
            assert res.status_code == 200
            body = res.json()
            assert body["paid"] is False
            assert body["status"] is None
        finally:
            app.dependency_overrides.clear()

    async def test_stranger_gets_404(self, db_session, owner, stranger):
        order = _make_order(owner.id)
        await SQLOrderRepository(db_session).create(order)
        _client_for(stranger, db_session)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ax:
                res = await ax.get(f"/api/v1/orders/{order.id}/payment")
            assert res.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestPostPaymentOwner:
    async def test_owner_can_init_own_payment(self, db_session, owner):
        order = _make_order(owner.id)
        await SQLOrderRepository(db_session).create(order)
        _client_for(owner, db_session)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ax:
                res = await ax.post(
                    f"/api/v1/orders/{order.id}/payment",
                    headers={"Idempotency-Key": "test-key-1"},
                )
            assert res.status_code == 200
            body = res.json()
            assert body["reference"] == f"mock_{order.id}"
            assert body["checkout_url"]
        finally:
            app.dependency_overrides.clear()

    async def test_stranger_cannot_init_payment(self, db_session, owner, stranger):
        order = _make_order(owner.id)
        await SQLOrderRepository(db_session).create(order)
        _client_for(stranger, db_session)
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ax:
                res = await ax.post(
                    f"/api/v1/orders/{order.id}/payment",
                    headers={"Idempotency-Key": "test-key-2"},
                )
            assert res.status_code == 404
        finally:
            app.dependency_overrides.clear()

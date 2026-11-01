"""Integration tests for PATCH /orders/{id}/paid (C1.0).

Covers:
    200 for cash orders
    200 for mercadopago orders without terminal status
    409 for already paid orders
    409 for mercadopago orders with terminal status (approved/rejected/failed)
    404 for non-existent orders
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
from api.v1.dependencies import require_admin
from data.db import get_db as get_db_orig
from data.models import Base
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod
from main import app

# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, lambda x: x, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


async def _admin_user():
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
    app.dependency_overrides[SQLOrderRepository] = override_get_order_repo
    app.dependency_overrides[require_admin] = _admin_user

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
async def cash_order(db_session):
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


@pytest_asyncio.fixture
async def mercadopago_order(db_session):
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


# ─── Tests ────────────────────────────────────────────────────────────


class TestPatchOrderPaid:
    """Tests for PATCH /orders/{id}/paid (C1.0)."""

    async def test_cash_order_marks_paid(self, client, cash_order):
        response = await client.patch(f"/api/v1/orders/{cash_order.id}/paid")
        assert response.status_code == 200
        data = response.json()
        assert data["paid"] is True

    async def test_cash_order_keeps_payment_status_and_reference_null(
        self, client, db_session, cash_order
    ):
        await client.patch(f"/api/v1/orders/{cash_order.id}/paid")
        stored = await SQLOrderRepository(db_session).get(cash_order.id)
        assert stored.paid is True
        assert stored.payment_status is None
        assert stored.payment_reference is None

    async def test_mercadopago_no_terminal_status_marks_paid(
        self, client, mercadopago_order
    ):
        response = await client.patch(f"/api/v1/orders/{mercadopago_order.id}/paid")
        assert response.status_code == 200
        data = response.json()
        assert data["paid"] is True

    async def test_already_paid_returns_409(self, client, cash_order):
        # First mark as paid
        await client.patch(f"/api/v1/orders/{cash_order.id}/paid")
        # Second attempt should fail
        response = await client.patch(f"/api/v1/orders/{cash_order.id}/paid")
        assert response.status_code == 409
        assert response.json()["detail"] == "order_already_paid"

    async def test_nonexistent_order_returns_404(self, client):
        response = await client.patch(
            "/api/v1/orders/nonexistent-paid/paid"
        )
        assert response.status_code == 404

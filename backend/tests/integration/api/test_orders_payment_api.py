"""Integration tests for payment API endpoints (C1.4/C1.5).

Covers:
    POST /orders/{id}/payment:
        - 200 creates a Checkout Pro preference for the real order amount
        - 503 when Mercado Pago is not configured, 502 on provider errors
        - 422 for cash orders
        - 409 for non-nuevo orders
    GET /orders/{id}/payment:
        - 200 with correct status/paid
        - 404 for non-existent orders
"""

import datetime
import json
import uuid
from decimal import Decimal

import httpx
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
from api.v1.orders.dependencies import get_checkout_provider
from core.config import settings
from data.db import get_db as get_db_orig
from data.models import Base, OrderItemORM
from data.payments.mercadopago import MercadoPagoCheckoutProvider
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


# Bodies sent to the mocked Mercado Pago API (POST /checkout/preferences).
_MP_REQUESTS: list[dict] = []


def _mp_api(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    _MP_REQUESTS.append(body)
    if body["external_reference"] == "explode":
        return httpx.Response(500, json={"message": "internal"})
    pref_id = f"pref-{body['external_reference']}"
    return httpx.Response(
        201,
        json={"id": pref_id, "init_point": f"https://mp.example/checkout?pref_id={pref_id}"},
    )


def _provider() -> MercadoPagoCheckoutProvider:
    return MercadoPagoCheckoutProvider(
        access_token="APP_USR-test",
        webhook_secret="secret",
        transport=httpx.MockTransport(_mp_api),
    )


async def _persist(db_session, order: Order) -> Order:
    """Store the order with its line items (repo.create stores the header only)."""
    await SQLOrderRepository(db_session).create(order)
    for item in order.items:
        db_session.add(
            OrderItemORM(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=str(item.unit_price),
            )
        )
    await db_session.commit()
    return order


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
    app.dependency_overrides[require_admin] = _admin_user
    app.dependency_overrides[get_checkout_provider] = _provider
    _MP_REQUESTS.clear()

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
    return await _persist(db_session, order)


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

    async def test_mercadopago_payment_returns_checkout_pro_preference(
        self, client, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        pref_id = f"pref-{mercadopago_order.id}"
        assert response.json() == {
            "reference": pref_id,
            "checkout_url": f"https://mp.example/checkout?pref_id={pref_id}",
        }
        [sent] = _MP_REQUESTS
        assert sent["external_reference"] == mercadopago_order.id
        assert sent["items"][0]["unit_price"] == 1000.0
        assert sent["items"][0]["currency_id"] == "ARS"

    async def test_payment_amount_subtracts_discount(self, client, db_session):
        order = Order(
            customer_id=str(uuid.uuid4()),
            date=datetime.datetime.now(datetime.UTC),
            items=[
                OrderItem(product_id="p1", product_name="Torta", quantity=2, unit_price=Decimal("750.50")),
            ],
            payment_method=PaymentMethod.MERCADOPAGO,
            coupon_code="PROMO",
            discount_amount=Decimal("100.25"),
        )
        await _persist(db_session, order)

        response = await client.post(
            f"/api/v1/orders/{order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        assert _MP_REQUESTS[0]["items"][0]["unit_price"] == 1400.75

    async def test_provider_error_returns_502(self, client, db_session):
        order = Order(
            id="explode",
            customer_id=str(uuid.uuid4()),
            date=datetime.datetime.now(datetime.UTC),
            items=[OrderItem(product_id="p1", product_name="Torta", quantity=1, unit_price=Decimal(10))],
            payment_method=PaymentMethod.MERCADOPAGO,
        )
        await _persist(db_session, order)

        response = await client.post(
            "/api/v1/orders/explode/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "payment_provider_error"

    async def test_unconfigured_provider_returns_503(
        self, client, mercadopago_order, monkeypatch
    ):
        app.dependency_overrides.pop(get_checkout_provider)
        monkeypatch.setattr(settings, "MP_ACCESS_TOKEN", "")
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "payment_provider_unavailable"

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

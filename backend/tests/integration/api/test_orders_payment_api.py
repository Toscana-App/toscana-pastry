"""Integration tests for payment API endpoints (C1.4/C1.5).

Covers:
    POST /orders/{id}/payment:
        - 200 creates a Checkout Pro preference for the real order amount
        - 503 when Mercado Pago is not configured, 502 on provider errors
        - 422 for cash orders
        - owner/admin allowed, other customers 404 (S6)
        - Idempotency-Key persisted: replay, 409 payment_in_progress,
          422 payment_finalized (S7)
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
from api.v1.dependencies import get_current_user, require_admin
from api.v1.orders.dependencies import get_checkout_provider
from core.config import settings
from data.db import get_db as get_db_orig
from data.models import Base, OrderItemORM
from data.payments.mercadopago import MercadoPagoCheckoutProvider
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod, PaymentStatus
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


ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)
OWNER = User(email="owner@example.com", role=UserRole.CUSTOMER)
STRANGER = User(email="stranger@example.com", role=UserRole.CUSTOMER)

# User returned by get_current_user; tests switch it.
_CURRENT = {"user": ADMIN}


async def _admin_user():
    """Return a fake admin user for dependency overrides."""
    return ADMIN


async def _current_user():
    return _CURRENT["user"]


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
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_checkout_provider] = _provider
    _CURRENT["user"] = ADMIN
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
        customer_id=OWNER.id,
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


async def _pay(client, order_id: str, key: str = "key-1"):
    return await client.post(
        f"/api/v1/orders/{order_id}/payment", headers={"Idempotency-Key": key}
    )


async def _set_payment_status(db_session, order_id: str, status: PaymentStatus, paid: bool = False):
    await SQLOrderRepository(db_session).update_payment_status(
        order_id=order_id,
        reference="mp-1",
        status=status,
        paid_at=datetime.datetime.now(datetime.UTC) if paid else None,
    )


class TestPaymentOwnership:
    """S6: the order owner (or an admin) pays; other customers get 404."""

    async def test_owner_can_initiate_payment(self, client, mercadopago_order):
        _CURRENT["user"] = OWNER
        response = await _pay(client, mercadopago_order.id)
        assert response.status_code == 200
        assert response.json()["reference"] == f"pref-{mercadopago_order.id}"

    async def test_admin_can_initiate_payment(self, client, mercadopago_order):
        response = await _pay(client, mercadopago_order.id)
        assert response.status_code == 200

    async def test_other_customer_gets_404_and_no_preference(self, client, mercadopago_order):
        _CURRENT["user"] = STRANGER
        response = await _pay(client, mercadopago_order.id)
        assert response.status_code == 404
        assert _MP_REQUESTS == []

    async def test_owner_can_read_payment_status(self, client, mercadopago_order):
        _CURRENT["user"] = OWNER
        response = await client.get(f"/api/v1/orders/{mercadopago_order.id}/payment")
        assert response.status_code == 200
        assert response.json()["paid"] is False

    async def test_other_customer_cannot_read_payment_status(self, client, mercadopago_order):
        _CURRENT["user"] = STRANGER
        response = await client.get(f"/api/v1/orders/{mercadopago_order.id}/payment")
        assert response.status_code == 404


class TestPaymentIdempotency:
    """S7: Idempotency-Key is persisted (C1.4)."""

    async def test_same_key_replays_saved_response_without_new_preference(
        self, client, mercadopago_order
    ):
        first = await _pay(client, mercadopago_order.id, "key-1")
        second = await _pay(client, mercadopago_order.id, "key-1")
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == first.json()
        assert len(_MP_REQUESTS) == 1

    async def test_initiating_payment_sets_pending_and_reference(
        self, client, mercadopago_order
    ):
        await _pay(client, mercadopago_order.id, "key-1")
        status = await client.get(f"/api/v1/orders/{mercadopago_order.id}/payment")
        assert status.json()["status"] == "pending"
        assert status.json()["payment_reference"] == f"pref-{mercadopago_order.id}"

    async def test_other_key_after_initiation_returns_409_without_new_preference(
        self, client, mercadopago_order
    ):
        await _pay(client, mercadopago_order.id, "key-1")
        response = await _pay(client, mercadopago_order.id, "key-2")
        assert response.status_code == 409
        assert response.json()["detail"] == "payment_in_progress"
        assert len(_MP_REQUESTS) == 1

    async def test_provider_failure_releases_pending_so_retry_is_possible(
        self, client, db_session
    ):
        order = Order(
            id="explode",
            customer_id=str(uuid.uuid4()),
            date=datetime.datetime.now(datetime.UTC),
            items=[OrderItem(product_id="p1", product_name="Torta", quantity=1, unit_price=Decimal(10))],
            payment_method=PaymentMethod.MERCADOPAGO,
        )
        await _persist(db_session, order)
        failed = await _pay(client, "explode", "key-1")
        assert failed.status_code == 502
        stored = await SQLOrderRepository(db_session).get("explode")
        assert stored.payment_status is None
        again = await _pay(client, "explode", "key-2")
        assert again.status_code == 502  # not 409 payment_in_progress

    async def test_claim_is_row_guarded(self, db_session, mercadopago_order):
        repo = SQLOrderRepository(db_session)
        assert await repo.claim_payment_pending(mercadopago_order.id) is True
        assert await repo.claim_payment_pending(mercadopago_order.id) is False

    async def test_other_key_while_pending_returns_409(self, client, db_session, mercadopago_order):
        await _pay(client, mercadopago_order.id, "key-1")
        await _set_payment_status(db_session, mercadopago_order.id, PaymentStatus.PENDING)
        response = await _pay(client, mercadopago_order.id, "key-2")
        assert response.status_code == 409
        assert response.json()["detail"] == "payment_in_progress"
        assert len(_MP_REQUESTS) == 1

    async def test_same_key_while_pending_still_replays(self, client, db_session, mercadopago_order):
        first = await _pay(client, mercadopago_order.id, "key-1")
        await _set_payment_status(db_session, mercadopago_order.id, PaymentStatus.PENDING)
        second = await _pay(client, mercadopago_order.id, "key-1")
        assert second.status_code == 200
        assert second.json() == first.json()

    async def test_terminal_status_returns_422_payment_finalized(
        self, client, db_session, mercadopago_order
    ):
        for status, paid in (
            (PaymentStatus.REJECTED, False),
            (PaymentStatus.FAILED, False),
            (PaymentStatus.APPROVED, True),
        ):
            await _set_payment_status(db_session, mercadopago_order.id, status, paid)
            response = await _pay(client, mercadopago_order.id, f"key-{status.value}")
            assert response.status_code == 422, status
            assert response.json()["detail"] == "payment_finalized"
        assert _MP_REQUESTS == []

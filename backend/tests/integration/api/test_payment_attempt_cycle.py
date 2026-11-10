
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import get_current_user, require_admin
from api.v1.orders.dependencies import get_checkout_provider
from api.v1.orders.dependencies import get_order_repository as get_order_repo_fn
from data.db import get_db as get_db_orig
from data.models import PaymentAttemptORM
from data.payments.mercadopago import MercadoPagoCheckoutProvider
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod, PaymentStatus
from main import app

WEBHOOK_SECRET = "test-webhook-secret"
REQUEST_ID = "req-1"

_MP_PAYMENTS: dict[str, dict] = {}


def _mp_api(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path == "/checkout/preferences":
        body = json.loads(request.content)
        pref_id = f"pref-{body['external_reference']}"
        return httpx.Response(
            201,
            json={
                "id": pref_id,
                "init_point": f"https://mp.example/checkout?pref_id={pref_id}",
            },
        )
    payment_id = request.url.path.rsplit("/", 1)[-1]
    payment = _MP_PAYMENTS.get(payment_id)
    if payment is None:
        return httpx.Response(404, json={"message": "not found"})
    return httpx.Response(200, json=payment)


def _provider() -> MercadoPagoCheckoutProvider:
    return MercadoPagoCheckoutProvider(
        access_token="APP_USR-test",
        webhook_secret=WEBHOOK_SECRET,
        transport=httpx.MockTransport(_mp_api),
    )


def _signature(data_id: str, request_id: str = REQUEST_ID, ts: int | None = None) -> str:
    ts = int(time.time()) if ts is None else ts
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)


async def _admin_user():
    return ADMIN


async def _current_user():
    return ADMIN


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
    app.dependency_overrides[get_order_repo_fn] = override_get_order_repo
    app.dependency_overrides[require_admin] = _admin_user
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_checkout_provider] = _provider
    _MP_PAYMENTS.clear()

    await SQLUserRepository(db_session).save(ADMIN)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def mercadopago_order(db_session):
    order = Order(
        customer_id=ADMIN.id,
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
    await repo.add(order)

    async def refresh():
        return await repo.get(order.id)

    order._refresh = refresh
    return order


def _set_payment(
    payment_id: str,
    status: str,
    order_id: str | None,
    amount: float = 1000,
    currency: str = "ARS",
) -> None:
    _MP_PAYMENTS[payment_id] = {
        "id": int(payment_id) if payment_id.isdigit() else payment_id,
        "status": status,
        "external_reference": order_id,
        "transaction_amount": amount,
        "currency_id": currency,
    }


async def _notify(client, payment_id: str):
    body = {"type": "payment", "action": "payment.updated", "data": {"id": payment_id}}
    return await client.post(
        "/api/v1/webhooks/mercadopago",
        content=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-request-id": REQUEST_ID,
            "x-signature": _signature(payment_id),
        },
    )


async def _attempts(db_session, order_id: str) -> list[PaymentAttemptORM]:
    result = await db_session.execute(
        select(PaymentAttemptORM).where(PaymentAttemptORM.order_id == order_id)
    )
    return list(result.scalars().all())


class TestAttemptCreation:

    async def test_attempt_reference_is_stored_in_attempts_table(
        self, client, db_session, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        attempt_reference = response.json()["reference"]

        attempts = await _attempts(db_session, mercadopago_order.id)
        assert [a.reference for a in attempts] == [attempt_reference]

    async def test_pending_order_has_no_payment_reference(
        self, client, mercadopago_order
    ):
        await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        refreshed = await mercadopago_order._refresh()
        assert refreshed.payment_status == PaymentStatus.PENDING
        assert refreshed.paid is False
        assert refreshed.payment_reference is None


class TestAttemptApproval:

    async def test_approved_attempt_sets_order_reference_to_attempt_reference(
        self, client, db_session, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        attempt_reference = response.json()["reference"]

        _set_payment(attempt_reference, "approved", mercadopago_order.id)
        webhook = await _notify(client, attempt_reference)
        assert webhook.status_code == 200

        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.paid_at is not None
        assert refreshed.payment_status == PaymentStatus.APPROVED
        assert refreshed.payment_reference == attempt_reference


class TestAttemptRejection:

    async def test_rejected_attempt_never_touches_order_reference(
        self, client, db_session, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        attempt_reference = response.json()["reference"]

        _set_payment(attempt_reference, "rejected", mercadopago_order.id)
        webhook = await _notify(client, attempt_reference)
        assert webhook.status_code == 200

        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.paid_at is None
        assert refreshed.payment_status == PaymentStatus.REJECTED
        assert refreshed.payment_reference is None

    async def test_failed_attempt_never_touches_order_reference(
        self, client, db_session, mercadopago_order
    ):
        response = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert response.status_code == 200
        attempt_reference = response.json()["reference"]

        _set_payment(attempt_reference, "cancelled", mercadopago_order.id)
        webhook = await _notify(client, attempt_reference)
        assert webhook.status_code == 200

        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.paid_at is None
        assert refreshed.payment_status == PaymentStatus.FAILED
        assert refreshed.payment_reference is None


class TestAttemptRecovery:

    async def test_approved_after_rejected_sets_reference_only_when_paid(
        self, client, db_session, mercadopago_order
    ):
        first = await client.post(
            f"/api/v1/orders/{mercadopago_order.id}/payment",
            headers={"Idempotency-Key": "key-1"},
        )
        assert first.status_code == 200
        first_reference = first.json()["reference"]

        _set_payment(first_reference, "rejected", mercadopago_order.id)
        await _notify(client, first_reference)
        refreshed = await mercadopago_order._refresh()
        assert refreshed.payment_status == PaymentStatus.REJECTED
        assert refreshed.payment_reference is None

        second_id = f"pay-{mercadopago_order.id}"
        _set_payment(second_id, "approved", mercadopago_order.id)
        await _notify(client, second_id)

        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED
        assert refreshed.payment_reference == second_id

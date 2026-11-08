"""Integration tests for POST /webhooks/mercadopago (C1.6, S1/S2).

The real MercadoPagoCheckoutProvider is used; only the Mercado Pago REST API
is replaced by an httpx.MockTransport serving ``GET /v1/payments/{id}``.

Covers:
    - Official x-signature (HMAC over id/request-id/ts manifest) → 200 / 401
    - Non-payment notifications → 200 no effect
    - Dedupe by (payment id, status); same payment with a new status applies
    - Out-of-order states: pending never overwrites approved
    - rejected/failed don't set paid; cash orders remain paid=false
    - Unknown order / provider failure handling
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal

import pytest_asyncio
import httpx
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
from api.v1.orders.dependencies import get_order_repository as get_order_repo_fn
from data.db import get_db as get_db_orig
from data.payments.mercadopago import MercadoPagoCheckoutProvider
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod, PaymentStatus
from main import app

# ─── Fixtures ─────────────────────────────────────────────────────────

WEBHOOK_SECRET = "test-webhook-secret"
REQUEST_ID = "req-1"

# Mercado Pago payments served by the mocked API: id -> payment JSON.
_MP_PAYMENTS: dict[str, dict] = {}
_MP_API_CALLS: list[str] = []


def _mp_api(request: httpx.Request) -> httpx.Response:
    _MP_API_CALLS.append(request.url.path)
    payment_id = request.url.path.rsplit("/", 1)[-1]
    if payment_id == "explode":
        return httpx.Response(500, json={"message": "internal"})
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
    app.dependency_overrides[get_order_repo_fn] = override_get_order_repo
    app.dependency_overrides[require_admin] = _admin_user
    app.dependency_overrides[get_checkout_provider] = _provider
    _MP_PAYMENTS.clear()
    _MP_API_CALLS.clear()

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
    await repo.add(order)  # header + line items: the amount check needs the total

    async def refresh():
        return await repo.get(order.id)

    order._refresh = refresh  # type: ignore[attr-defined]
    return order


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

    async def refresh():
        return await repo.get(order.id)

    order._refresh = refresh  # type: ignore[attr-defined]
    return order


# ─── Helpers ──────────────────────────────────────────────────────────


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


async def _notify(
    client,
    payment_id: str,
    *,
    type_: str = "payment",
    signature: str | None = "auto",
    request_id: str = REQUEST_ID,
):
    body = {"type": type_, "action": f"{type_}.updated", "data": {"id": payment_id}}
    headers = {"Content-Type": "application/json", "x-request-id": request_id}
    if signature == "auto":
        signature = _signature(payment_id)
    if signature is not None:
        headers["x-signature"] = signature
    return await client.post(
        "/api/v1/webhooks/mercadopago",
        content=json.dumps(body).encode(),
        headers=headers,
    )


# ─── Tests ────────────────────────────────────────────────────────────


class TestWebhookSignature:
    async def test_valid_signature_returns_200_ok(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        response = await _notify(client, "1001")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_missing_signature_returns_401(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        response = await _notify(client, "1001", signature=None)
        assert response.status_code == 401
        assert (await mercadopago_order._refresh()).paid is False

    async def test_invalid_signature_returns_401(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        response = await _notify(client, "1001", signature=f"ts={int(time.time())},v1={'0' * 64}")
        assert response.status_code == 401
        assert (await mercadopago_order._refresh()).paid is False

    async def test_signature_for_other_request_id_returns_401(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        response = await _notify(client, "1001", signature=_signature("1001", "req-other"))
        assert response.status_code == 401

    async def test_invalid_json_returns_401(self, client):
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=b"not json",
            headers={"x-signature": _signature("1001"), "x-request-id": REQUEST_ID},
        )
        assert response.status_code == 401


class TestWebhookTopics:
    async def test_non_payment_topic_is_ignored(self, client, mercadopago_order):
        response = await _notify(client, "555", type_="merchant_order")
        assert response.status_code == 200
        assert _MP_API_CALLS == []
        assert (await mercadopago_order._refresh()).payment_status is None

    async def test_payment_of_unknown_order_returns_200_no_effect(self, client):
        _set_payment("1001", "approved", "no-such-order")
        response = await _notify(client, "1001")
        assert response.status_code == 200

    async def test_payment_without_external_reference_returns_200(self, client):
        _set_payment("1001", "approved", None)
        response = await _notify(client, "1001")
        assert response.status_code == 200

    async def test_provider_failure_returns_502_so_mp_retries(self, client):
        response = await _notify(client, "explode")
        assert response.status_code == 502


class TestWebhookDedupe:
    async def test_replay_returns_200_no_effect(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        first = await _notify(client, "1001")
        paid_at = (await mercadopago_order._refresh()).paid_at
        second = await _notify(client, "1001")
        assert first.status_code == 200
        assert second.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.paid_at == paid_at

    async def test_same_payment_pending_then_approved_applies(self, client, mercadopago_order):
        _set_payment("1001", "pending", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.payment_status == PaymentStatus.PENDING
        assert refreshed.paid is False

        _set_payment("1001", "approved", mercadopago_order.id)
        response = await _notify(client, "1001")
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.payment_status == PaymentStatus.APPROVED
        assert refreshed.paid is True
        assert refreshed.payment_reference == "1001"

    async def test_pending_does_not_overwrite_approved(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1002", "pending", mercadopago_order.id)
        response = await _notify(client, "1002")
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED


class TestWebhookPayload:
    async def _post(self, client, body: bytes, data_id: str = "1001"):
        return await client.post(
            "/api/v1/webhooks/mercadopago",
            content=body,
            headers={"x-signature": _signature(data_id), "x-request-id": REQUEST_ID},
        )

    async def test_non_object_payload_never_reaches_500(self, client):
        # The signature manifest needs data.id, so a non-object body is
        # rejected as unverifiable before any payload handling.
        response = await self._post(client, b"[1, 2]")
        assert response.status_code in (401, 422)

    async def test_payment_with_empty_id_returns_422(self, client):
        response = await self._post(client, b'{"type": "payment", "data": {"id": " "}}', " ")
        assert response.status_code == 422
        assert _MP_API_CALLS == []


class TestWebhookPriorityAndAtomicity:
    async def test_pending_after_rejected_does_not_overwrite(self, client, mercadopago_order):
        _set_payment("1001", "rejected", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1002", "pending", mercadopago_order.id)
        await _notify(client, "1002")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.payment_status == PaymentStatus.REJECTED
        assert refreshed.payment_reference == "1001"

    async def test_pending_after_failed_does_not_overwrite(self, client, mercadopago_order):
        _set_payment("1001", "cancelled", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1002", "pending", mercadopago_order.id)
        await _notify(client, "1002")
        assert (await mercadopago_order._refresh()).payment_status == PaymentStatus.FAILED

    async def test_rejected_after_approved_never_reverts_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1002", "rejected", mercadopago_order.id)
        await _notify(client, "1002")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED
        assert refreshed.payment_reference == "1001"

    async def test_approved_after_rejected_applies(self, client, mercadopago_order):
        _set_payment("1001", "rejected", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1002", "approved", mercadopago_order.id)
        await _notify(client, "1002")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED

    async def test_second_approved_payment_does_not_overwrite_paid_at_or_reference(
        self, client, mercadopago_order
    ):
        _set_payment("1001", "approved", mercadopago_order.id)
        await _notify(client, "1001")
        first = await mercadopago_order._refresh()
        _set_payment("1002", "approved", mercadopago_order.id)
        await _notify(client, "1002")
        second = await mercadopago_order._refresh()
        assert second.paid_at == first.paid_at
        assert second.payment_reference == "1001"

    async def test_event_and_effect_are_one_transaction_and_dedupe_is_atomic(
        self, db_session, mercadopago_order
    ):
        repo = SQLOrderRepository(db_session)
        now = datetime.datetime.now(datetime.UTC)
        args = dict(
            event_id="1001:approved",
            order_id=mercadopago_order.id,
            provider_payment_id="1001",
            status=PaymentStatus.APPROVED,
            paid_at=now,
        )
        assert await repo.apply_payment_event(**args) is True
        assert await repo.get_payment_event("1001:approved") is True
        order = await repo.get(mercadopago_order.id)
        assert order.paid is True

        # Replay of the same event: no effect, no error.
        assert await repo.apply_payment_event(**{**args, "paid_at": now + datetime.timedelta(hours=1)}) is False
        assert (await repo.get(mercadopago_order.id)).paid_at == order.paid_at


class TestWebhookStates:
    async def test_approved_sets_paid_true(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED
        assert refreshed.payment_reference == "1001"

    async def test_rejected_does_not_set_paid(self, client, mercadopago_order):
        _set_payment("1001", "rejected", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.REJECTED

    async def test_cancelled_maps_to_failed_without_paid(self, client, mercadopago_order):
        _set_payment("1001", "cancelled", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.FAILED

    async def test_refund_after_approved_does_not_revert_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        await _notify(client, "1001")
        _set_payment("1001", "refunded", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED

    async def test_in_process_is_pending(self, client, mercadopago_order):
        _set_payment("1001", "in_process", mercadopago_order.id)
        await _notify(client, "1001")
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.PENDING


class TestWebhookCash:
    async def test_cash_order_remains_paid_false(self, client, cash_order):
        _set_payment("1001", "approved", cash_order.id)
        response = await _notify(client, "1001")
        assert response.status_code == 200
        refreshed = await cash_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status is None


class TestWebhookAntiReplayAndAmount:
    async def test_stale_ts_returns_401_and_does_not_mark_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        stale = _signature("1001", ts=int(time.time()) - 6 * 60)
        response = await _notify(client, "1001", signature=stale)
        assert response.status_code == 401
        assert (await mercadopago_order._refresh()).paid is False

    async def test_ts_within_5_minutes_is_accepted(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        recent = _signature("1001", ts=int(time.time()) - 4 * 60)
        assert (await _notify(client, "1001", signature=recent)).status_code == 200
        assert (await mercadopago_order._refresh()).paid is True

    async def test_lower_amount_is_not_marked_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id, amount=1)
        response = await _notify(client, "1001")
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status is None

    async def test_other_currency_is_not_marked_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id, currency="USD")
        response = await _notify(client, "1001")
        assert response.status_code == 200
        assert (await mercadopago_order._refresh()).paid is False

    async def test_missing_amount_is_not_marked_paid(self, client, mercadopago_order):
        _set_payment("1001", "approved", mercadopago_order.id)
        del _MP_PAYMENTS["1001"]["transaction_amount"]
        assert (await _notify(client, "1001")).status_code == 200
        assert (await mercadopago_order._refresh()).paid is False

    async def test_amount_is_compared_after_discount(self, client, db_session):
        order = Order(
            customer_id=str(uuid.uuid4()),
            date=datetime.datetime.now(datetime.UTC),
            items=[OrderItem("p1", "Torta", 1, Decimal(1000))],
            payment_method=PaymentMethod.MERCADOPAGO,
            discount_amount=Decimal(100),
        )
        repo = SQLOrderRepository(db_session)
        await repo.add(order)
        _set_payment("1001", "approved", order.id, amount=1000)  # ignores discount
        await _notify(client, "1001")
        assert (await repo.get(order.id)).paid is False
        _set_payment("1002", "approved", order.id, amount=900)
        await _notify(client, "1002")
        assert (await repo.get(order.id)).paid is True

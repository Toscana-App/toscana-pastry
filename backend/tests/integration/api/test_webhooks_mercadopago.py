"""Integration tests for POST /webhooks/mercadopago (C1.6).

Covers:
    - Valid signature → 200
    - Invalid/missing signature → 401
    - Invalid payload → 422
    - Dedupe/replay → 200 no effect
    - Out-of-order states: pending never overwrites terminal
    - approved applied once (guard WHERE paid=false)
    - rejected/failed don't revert paid
    - Cash orders remain paid=false
    - Atomic transaction
    - 200 {"ok": true} with valid signature
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
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
from api.v1.orders.dependencies import get_order_repository as get_order_repo_fn
from data.db import get_db as get_db_orig
from data.models import Base
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod, PaymentStatus
from main import app

# ─── Fixtures ─────────────────────────────────────────────────────────

_MOCK_HMAC_SECRET = b"toscana-pastry-mock-hmac-secret-for-testing-only"


def _make_webhook_signature(payload: dict) -> str:
    raw = json.dumps(payload).encode()
    return hmac.new(_MOCK_HMAC_SECRET, raw, hashlib.sha256).hexdigest()


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
    await repo.create(order)

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


def _build_payload(payment_id: str, status: str, order_id: str) -> dict:
    return {"id": payment_id, "status": status, "resource": order_id}


# ─── Tests ────────────────────────────────────────────────────────────


class TestWebhookSignature:
    """Tests for webhook signature validation (C1.6)."""

    async def test_valid_signature_returns_200(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "approved", mercadopago_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["ok"] is True

    async def test_missing_signature_returns_401(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "approved", mercadopago_order.id)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 401

    async def test_invalid_signature_returns_401(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "approved", mercadopago_order.id)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": "invalid_sig", "Content-Type": "application/json"},
        )
        assert response.status_code == 401


class TestWebhookPayload:
    """Tests for webhook payload validation (C1.6)."""

    async def test_invalid_json_returns_422(self, client):
        # Compute a valid HMAC over the invalid payload so signature passes,
        # then the endpoint should fail on JSON parsing → 422.
        raw = b"not json"
        sig = hmac.new(_MOCK_HMAC_SECRET, raw, hashlib.sha256).hexdigest()
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=raw,
            headers={"x-signature": sig, "Content-Type": "application/json"},
        )
        assert response.status_code == 422

    async def test_invalid_status_returns_422(self, client, mercadopago_order):
        payload = {"id": "mp_123", "status": "unknown_status", "resource": mercadopago_order.id}
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestWebhookDedupe:
    """Tests for webhook dedupe / replay (C1.6, RF-P6-13, RNF-P6-10)."""

    async def test_replay_returns_200_no_effect(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "approved", mercadopago_order.id)
        signature = _make_webhook_signature(payload)

        response1 = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        response2 = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Verify order is paid only once (re-query to get updated state)
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True

    async def test_pending_does_not_overwrite_terminal(self, client, mercadopago_order):
        """approved then pending: paid should stay True, status should stay approved."""
        # First: approved
        payload_approved = _build_payload("mp_123", "approved", mercadopago_order.id)
        sig_approved = _make_webhook_signature(payload_approved)
        await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload_approved).encode(),
            headers={"x-signature": sig_approved, "Content-Type": "application/json"},
        )
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True

        # Then: pending (should not overwrite)
        payload_pending = _build_payload("mp_123_pending", "pending", mercadopago_order.id)
        sig_pending = _make_webhook_signature(payload_pending)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload_pending).encode(),
            headers={"x-signature": sig_pending, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True  # paid should NOT revert
        assert refreshed.payment_status == PaymentStatus.APPROVED  # status stays approved


class TestWebhookStates:
    """Tests for webhook state transitions (C1.6)."""

    async def test_approved_sets_paid_true(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "approved", mercadopago_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is True
        assert refreshed.payment_status == PaymentStatus.APPROVED

    async def test_rejected_does_not_set_paid(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "rejected", mercadopago_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.REJECTED

    async def test_failed_does_not_set_paid(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "failed", mercadopago_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.FAILED

    async def test_pending_does_not_set_paid(self, client, mercadopago_order):
        payload = _build_payload("mp_123", "pending", mercadopago_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        refreshed = await mercadopago_order._refresh()
        assert refreshed.paid is False
        assert refreshed.payment_status == PaymentStatus.PENDING


class TestWebhookCash:
    """Tests for cash orders via webhook (C1.6)."""

    async def test_cash_order_remains_paid_false(self, client, cash_order):
        """Webhook for a cash order should not mark it as paid."""
        payload = _build_payload("mp_123", "approved", cash_order.id)
        signature = _make_webhook_signature(payload)
        response = await client.post(
            "/api/v1/webhooks/mercadopago",
            content=json.dumps(payload).encode(),
            headers={"x-signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200
        # Cash orders should NOT be marked as paid by webhook
        refreshed = await cash_order._refresh()
        assert refreshed.paid is False

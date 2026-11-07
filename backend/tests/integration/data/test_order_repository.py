"""Integration tests for SQLOrderRepository payment operations (C1.2).

Covers:
    - update_payment_status: fields are persisted correctly
    - record_payment_event: dedupe by event id ("{payment_id}:{status}")
    - get_payment_event: replay does not duplicate
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data.repositories.sql_order_repository import SQLOrderRepository
from domain.order import Order, OrderItem, PaymentMethod, PaymentStatus


@pytest_asyncio.fixture
async def order_with_repo(db_session):
    """Create an MP order and return (order, repo)."""
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
    return order, repo


class TestUpdatePaymentStatus:
    """Tests for update_payment_status (C1.2)."""

    async def test_updates_reference_and_status(self, order_with_repo):
        order, repo = order_with_repo
        result = await repo.update_payment_status(
            order_id=order.id,
            reference="mp_456",
            status=PaymentStatus.PENDING,
            paid_at=None,
        )
        assert result is not None
        assert result.payment_reference == "mp_456"
        assert result.payment_status == PaymentStatus.PENDING

    async def test_updates_paid_at_when_provided(self, order_with_repo):
        order, repo = order_with_repo
        now = datetime.datetime.now(datetime.UTC)
        result = await repo.update_payment_status(
            order_id=order.id,
            reference="mp_789",
            status=PaymentStatus.APPROVED,
            paid_at=now,
        )
        assert result is not None
        assert result.paid_at == now
        assert result.paid is True

    async def test_returns_none_for_missing_order(self, order_with_repo):
        _, repo = order_with_repo
        result = await repo.update_payment_status(
            order_id="nonexistent-id",
            reference="mp_000",
            status=PaymentStatus.PENDING,
            paid_at=None,
        )
        assert result is None


class TestRecordPaymentEvent:
    """Tests for record_payment_event dedupe (C1.2, RF-P6-13)."""

    async def test_first_insert_succeeds(self, order_with_repo):
        order, repo = order_with_repo
        result = await repo.record_payment_event(
            event_id="evt_001",
            order_id=order.id,
            provider_payment_id="mp_dedupe_test",
            status=PaymentStatus.PENDING,
        )
        assert result is True

    async def test_duplicate_event_id_returns_false(self, order_with_repo):
        order, repo = order_with_repo
        await repo.record_payment_event(
            event_id="mp_dedupe_test:pending",
            order_id=order.id,
            provider_payment_id="mp_dedupe_test",
            status=PaymentStatus.PENDING,
        )
        # Replay of the same event (same payment + status) — rejected
        result = await repo.record_payment_event(
            event_id="mp_dedupe_test:pending",
            order_id=order.id,
            provider_payment_id="mp_dedupe_test",
            status=PaymentStatus.PENDING,
        )
        assert result is False

    async def test_same_payment_new_status_succeeds(self, order_with_repo):
        """S2: Mercado Pago notifies one payment several times (pending → approved)."""
        order, repo = order_with_repo
        r1 = await repo.record_payment_event(
            event_id="mp_dedupe_test:pending",
            order_id=order.id,
            provider_payment_id="mp_dedupe_test",
            status=PaymentStatus.PENDING,
        )
        r2 = await repo.record_payment_event(
            event_id="mp_dedupe_test:approved",
            order_id=order.id,
            provider_payment_id="mp_dedupe_test",
            status=PaymentStatus.APPROVED,
        )
        assert r1 is True
        assert r2 is True

    async def test_different_provider_ids_both_succeed(self, order_with_repo):
        order, repo = order_with_repo
        r1 = await repo.record_payment_event(
            event_id="evt_004a",
            order_id=order.id,
            provider_payment_id="mp_first",
            status=PaymentStatus.PENDING,
        )
        r2 = await repo.record_payment_event(
            event_id="evt_004b",
            order_id=order.id,
            provider_payment_id="mp_second",
            status=PaymentStatus.APPROVED,
        )
        assert r1 is True
        assert r2 is True


class TestGetPaymentEvent:
    """Tests for get_payment_event dedupe check."""

    async def test_existing_event_returns_true(self, order_with_repo):
        order, repo = order_with_repo
        await repo.record_payment_event(
            event_id="mp_check_exist:approved",
            order_id=order.id,
            provider_payment_id="mp_check_exist",
            status=PaymentStatus.APPROVED,
        )
        assert await repo.get_payment_event("mp_check_exist:approved") is True
        assert await repo.get_payment_event("mp_check_exist:pending") is False

    async def test_nonexisting_event_returns_false(self, order_with_repo):
        _, repo = order_with_repo
        result = await repo.get_payment_event("mp_never_seen")
        assert result is False

"""Unit tests for lazy payment expiry (24 h) -- injectable clock, no sleeps."""

import datetime
from decimal import Decimal

from domain.order import (
    PAYMENT_EXPIRY,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    is_payment_expired,
)

T0 = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)


def _order(**kw) -> Order:
    base = dict(
        customer_id="c",
        date=T0,
        items=[OrderItem("p", "Torta", 1, Decimal(100))],
        payment_method=PaymentMethod.MERCADOPAGO,
        payment_status=PaymentStatus.PENDING,
        created_at=T0,
    )
    base.update(kw)
    return Order(**base)


def test_not_expired_just_before_24h():
    assert not is_payment_expired(_order(), T0 + PAYMENT_EXPIRY - datetime.timedelta(seconds=1))


def test_expired_at_24h():
    assert is_payment_expired(_order(), T0 + PAYMENT_EXPIRY)


def test_naive_created_at_is_treated_as_utc():
    order = _order(created_at=T0.replace(tzinfo=None))
    assert is_payment_expired(order, T0 + PAYMENT_EXPIRY)


def test_only_pending_unpaid_mercadopago_nuevo_orders_expire():
    late = T0 + datetime.timedelta(days=2)
    assert not is_payment_expired(_order(payment_status=None), late)
    assert not is_payment_expired(_order(payment_status=PaymentStatus.APPROVED), late)
    assert not is_payment_expired(_order(paid_at=T0), late)
    assert not is_payment_expired(_order(status=OrderStatus.CONFIRMADO), late)
    assert not is_payment_expired(
        _order(payment_method=PaymentMethod.CASH, payment_status=None), late
    )

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from domain.order import (
    PAYMENT_EXPIRY,
    DeliveryMode,
    Order,
    OrderItem,
    PaymentMethod,
    PaymentStatus,
    is_payment_expired,
)

T0 = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)


def _items() -> list[OrderItem]:
    return [
        OrderItem(
            product_id="p1",
            product_name="Torta",
            quantity=1,
            unit_price=Decimal(1000),
        )
    ]


def _order(**overrides: object) -> Order:
    base: dict[str, object] = {
        "customer_id": "cust-1",
        "date": T0,
        "items": _items(),
        "payment_method": PaymentMethod.TRANSFER,
        "created_at": T0,
    }
    base.update(overrides)
    return Order(**base)


class TestPlacePortalTransfer:
    def test_place_portal_with_transfer(self):
        order = Order.place_portal(
            customer_id="cust-1",
            date=datetime.datetime.now(datetime.UTC),
            items=_items(),
            payment_method=PaymentMethod.TRANSFER,
            delivery_mode=DeliveryMode.DELIVERY,
            delivery_address="Calle 1",
        )
        assert order.payment_method == PaymentMethod.TRANSFER
        assert order.paid is False
        assert order.payment_status is None


class TestTransferPaymentGuards:
    def test_transfer_never_expires(self):
        late = T0 + PAYMENT_EXPIRY + datetime.timedelta(days=1)
        assert is_payment_expired(_order(), late) is False
        assert is_payment_expired(
            _order(payment_status=PaymentStatus.PENDING), late
        ) is False

    def test_mark_cash_payment_rejects_transfer(self):
        with pytest.raises(ValueError, match="only for cash orders"):
            _order().mark_cash_payment()

    def test_confirm_payment_manual_on_transfer(self):
        order = _order()
        order.confirm_payment(reference="manual", status=PaymentStatus.APPROVED)
        assert order.paid is True
        assert order.payment_reference == "manual"
        assert order.payment_status == PaymentStatus.APPROVED
        assert order.paid_at is not None

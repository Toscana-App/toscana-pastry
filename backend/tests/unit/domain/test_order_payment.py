
import datetime
from decimal import Decimal

import pytest

from domain.order import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)


def _make_order(**overrides):
    return Order(
        customer_id="cust-1",
        date=datetime.datetime.now(datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal(1000),
            )
        ],
        **overrides,
    )


class TestPaymentMethodImmutable:

    def test_can_set_mercadopago_on_nuevo(self):
        order = _make_order()
        assert order.payment_method == PaymentMethod.CASH
        order.init_mercadopago()
        assert order.payment_method == PaymentMethod.MERCADOPAGO

    def test_cannot_switch_mercadopago_after_confirmation(self):
        order = _make_order(status=OrderStatus.CONFIRMADO)
        with pytest.raises(ValueError, match="immutable"):
            order.init_mercadopago()

    def test_cannot_switch_mercadopago_on_nuevo_if_already_mp(self):
        order = _make_order()
        order.init_mercadopago()
        order.init_mercadopago()
        assert order.payment_method == PaymentMethod.MERCADOPAGO


class TestPaidMonotonic:

    def test_paid_is_false_by_default(self):
        order = _make_order()
        assert order.paid is False

    def test_cash_mark_payment_sets_paid_true(self):
        order = _make_order()
        order.mark_cash_payment()
        assert order.paid is True
        assert order.paid_at is not None

    def test_cash_cannot_double_mark(self):
        order = _make_order()
        order.mark_cash_payment()
        with pytest.raises(ValueError, match="already paid"):
            order.mark_cash_payment()

    def test_cash_cannot_use_confirm_payment(self):
        order = _make_order(payment_method=PaymentMethod.CASH)
        with pytest.raises(ValueError, match="Cash orders"):
            order.confirm_payment(reference="ref", status=PaymentStatus.APPROVED)

    def test_confirm_payment_sets_all_fields(self):
        order = _make_order(payment_method=PaymentMethod.MERCADOPAGO)
        order.confirm_payment(
            reference="mp_123",
            status=PaymentStatus.APPROVED,
        )
        assert order.paid is True
        assert order.payment_reference == "mp_123"
        assert order.payment_status == PaymentStatus.APPROVED
        assert order.paid_at is not None

    def test_confirm_payment_cannot_revert(self):
        order = _make_order(payment_method=PaymentMethod.MERCADOPAGO)
        order.confirm_payment(
            reference="mp_123",
            status=PaymentStatus.APPROVED,
        )
        with pytest.raises(ValueError, match="already paid"):
            order.confirm_payment(
                reference="mp_456",
                status=PaymentStatus.REJECTED,
            )

    def test_mercadopago_cannot_use_mark_cash_payment(self):
        order = _make_order(payment_method=PaymentMethod.MERCADOPAGO)
        with pytest.raises(ValueError, match="only for cash orders"):
            order.mark_cash_payment()


class TestCashPaymentStatusNull:

    def test_cash_order_has_null_payment_status(self):
        order = _make_order(payment_method=PaymentMethod.CASH)
        assert order.payment_status is None

    def test_mark_cash_payment_does_not_set_payment_status(self):
        order = _make_order(payment_method=PaymentMethod.CASH)
        order.mark_cash_payment()
        assert order.payment_status is None

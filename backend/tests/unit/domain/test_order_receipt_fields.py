import datetime
from decimal import Decimal

import pytest

from domain.order import Order, OrderItem, PaymentMethod


def _order(payment_method=PaymentMethod.TRANSFER, **kwargs) -> Order:
    return Order(
        customer_id="c1",
        date=datetime.datetime.now(datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal("1000"),
            )
        ],
        payment_method=payment_method,
        **kwargs,
    )


class TestReceiptFields:

    def test_transfer_order_accepts_receipt_fields(self):
        now = datetime.datetime.now(datetime.UTC)
        order = _order(
            receipt_file="abc.jpg",
            receipt_content_type="image/jpeg",
            receipt_size_bytes=2048,
            receipt_uploaded_at=now,
            receipt_viewed_at=now,
        )
        assert order.receipt_file == "abc.jpg"
        assert order.receipt_uploaded_at == now

    def test_transfer_order_defaults_without_receipt(self):
        order = _order()
        assert order.receipt_file is None
        assert order.receipt_content_type is None
        assert order.receipt_size_bytes is None
        assert order.receipt_uploaded_at is None
        assert order.receipt_viewed_at is None
        assert order.receipt_deleted_at is None

    def test_deleted_state_keeps_deleted_at(self):
        now = datetime.datetime.now(datetime.UTC)
        order = _order(receipt_deleted_at=now)
        assert order.receipt_deleted_at == now

    @pytest.mark.parametrize(
        "method",
        [PaymentMethod.CASH, PaymentMethod.MERCADOPAGO],
    )
    def test_non_transfer_order_rejects_receipt_fields(self, method):
        with pytest.raises(ValueError):
            _order(payment_method=method, receipt_file="abc.jpg")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"receipt_content_type": "application/pdf"},
            {"receipt_size_bytes": 1024},
            {"receipt_uploaded_at": datetime.datetime.now(datetime.UTC)},
            {"receipt_viewed_at": datetime.datetime.now(datetime.UTC)},
            {"receipt_deleted_at": datetime.datetime.now(datetime.UTC)},
        ],
    )
    def test_cash_order_rejects_every_receipt_field(self, kwargs):
        with pytest.raises(ValueError):
            _order(payment_method=PaymentMethod.CASH, **kwargs)

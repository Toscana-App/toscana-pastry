
from __future__ import annotations

import datetime
from decimal import Decimal

from domain.order import Order, OrderItem, OrderStatus


def _make_order(**overrides):
    kwargs = {
        "customer_id": "cust-1",
        "date": datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        "items": [
            OrderItem(product_id="p1", product_name="Torta", quantity=2, unit_price=Decimal(500)),
        ],
    }
    kwargs.update(overrides)
    return Order(**kwargs)


class TestOrderCreation:

    def test_default_id_is_uuid(self):
        order = _make_order()
        assert order.id is not None
        assert len(order.id) == 36

    def test_default_status_is_nuevo(self):
        order = _make_order()
        assert order.status == OrderStatus.NUEVO

    def test_default_payment_method_is_cash(self):
        from domain.order import PaymentMethod
        order = _make_order()
        assert order.payment_method == PaymentMethod.CASH

    def test_created_at_is_set(self):
        order = _make_order()
        assert order.created_at is not None


class TestOrderItemTotal:

    def test_single_item_total(self):
        item = OrderItem(product_id="p1", product_name="Torta", quantity=1, unit_price=Decimal(1000))
        assert item.total == Decimal(1000)

    def test_multi_quantity_total(self):
        item = OrderItem(product_id="p1", product_name="Alfajor", quantity=10, unit_price=Decimal(200))
        assert item.total == Decimal(2000)

    def test_decimal_precision(self):
        item = OrderItem(product_id="p1", product_name="Bizcochuelo", quantity=3, unit_price=Decimal(1500.50))
        assert item.total == Decimal(4501.50)


class TestOrderTotal:

    def test_single_item_order_total(self):
        order = _make_order()
        assert order.total == Decimal(1000)

    def test_multi_item_order_total(self):
        items = [
            OrderItem(product_id="p1", product_name="Torta", quantity=1, unit_price=Decimal(2000)),
            OrderItem(product_id="p2", product_name="Alfajor", quantity=12, unit_price=Decimal(150)),
        ]
        order = _make_order(items=items)
        assert order.total == Decimal(3800)





import datetime
from decimal import Decimal

from domain.order import (
    DeliveryMode,
    Order,
    OrderItem,
    PaymentMethod,
)


def _order(**overrides: object) -> Order:
    base: dict[str, object] = {
        "customer_id": "cust-1",
        "date": datetime.datetime(2026, 11, 10),
        "items": [
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal(1000),
            )
        ],
    }
    base.update(overrides)
    return Order(**base)


class TestOrderCode:
    def test_code_format(self):
        order = _order()
        assert order.code.startswith("TP")
        assert len(order.code) == 8
        assert order.code[2:].isalnum()
        assert order.code == order.code.upper()

    def test_codes_are_unique(self):
        codes = {_order().code for _ in range(50)}
        assert len(codes) == 50


class TestDeliveryMode:
    def test_default_is_delivery(self):
        assert _order().delivery_mode == DeliveryMode.DELIVERY

    def test_domain_allows_empty_address_backward_compat(self):
        order = _order(delivery_mode=DeliveryMode.DELIVERY, delivery_address="")
        assert order.delivery_address == ""

    def test_delivery_with_address_is_valid(self):
        order = _order(delivery_address="Calle 123, CABA")
        assert order.delivery_address == "Calle 123, CABA"

    def test_pickup_normalizes_address_to_none(self):
        order = _order(
            delivery_mode=DeliveryMode.PICKUP,
            delivery_address="Calle 123",
        )
        assert order.delivery_address is None
        assert order.delivery_mode == DeliveryMode.PICKUP

    def test_pickup_without_address_is_valid(self):
        order = _order(delivery_mode=DeliveryMode.PICKUP)
        assert order.delivery_address is None


class TestCouponSnapshot:
    def test_defaults(self):
        order = _order()
        assert order.coupon_code is None
        assert order.discount_amount is None

    def test_snapshot_values(self):
        order = _order(
            coupon_code="VERANO10",
            discount_amount=Decimal("140.00"),
        )
        assert order.coupon_code == "VERANO10"
        assert order.discount_amount == Decimal("140.00")


class TestExistingBehaviorUnchanged:
    def test_positional_and_keyword_creation_still_works(self):
        order = Order(
            customer_id="c",
            date=datetime.datetime(2026, 11, 10),
            items=[],
            delivery_mode=DeliveryMode.PICKUP,
            payment_method=PaymentMethod.CASH,
        )
        assert order.paid is False
        assert order.payment_status is None

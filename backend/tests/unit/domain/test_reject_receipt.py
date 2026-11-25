import datetime
from decimal import Decimal

import pytest

from domain.models import Ingredient
from domain.order import Order, OrderItem, PaymentMethod
from domain.order_states import OrderStatus
from domain.orders import (
    InsufficientOrderStockError,
    OrderItemSnapshot,
    OrderItemSnapshotLine,
)
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptNotFoundError,
    ReceiptOrderNotCancellableError,
    ReceiptPaymentNotPendingError,
)
from domain.use_cases.reject_receipt import RejectReceipt


def _ing(id_, stock) -> Ingredient:
    return Ingredient(
        name=id_, unit="g", price_per_unit=Decimal("1"), stock_qty=Decimal(stock), id=id_
    )


def _order(
    status: str = "new",
    payment_status: PaymentStatus | None = PaymentStatus.PENDING,
    receipt: bool = True,
) -> Order:
    snapshots = {
        "item1": OrderItemSnapshot(
            lines=(
                OrderItemSnapshotLine(
                    ingredient_id="flour",
                    ingredient_name="flour",
                    qty=Decimal("500"),
                    unit="g",
                    cost=Decimal("0"),
                ),
            )
        )
    }
    return Order(
        customer_id="c1",
        date=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Pastel",
                quantity=1,
                unit_price=Decimal("100"),
            )
        ],
        status=OrderStatus(status),
        payment_method=PaymentMethod.TRANSFER,
        payment_status=payment_status,
        receipt_file="o1.pdf" if receipt else None,
        receipt_content_type="application/pdf" if receipt else None,
        receipt_uploaded_at=datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.UTC)
        if receipt
        else None,
        snapshots=snapshots,
    )


class FakeReceiptStore:
    def __init__(self, order, ingredients):
        self.order = order
        self.ingredients = {i.id: i for i in ingredients}
        self.movements = []
        self.status_set = None
        self.payment_set = None
        self.audit_events = []
        self.committed = False
        self.rolled_back = False

    async def lock_order(self, order_id):
        return self.order

    async def lock_ingredients(self, ids):
        return {i: self.ingredients[i] for i in ids if i in self.ingredients}

    async def apply_movements(self, changes):
        for updated, movement in changes:
            self.ingredients[updated.id] = updated
            self.movements.append(movement)

    async def set_status(self, order_id, status):
        self.status_set = status

    async def set_payment(self, order_id, *, reference, status, paid_at):
        self.payment_set = (reference, status, paid_at)

    async def record_payment_event(
        self, event_id, order_id, provider_payment_id, status
    ):
        self.audit_events.append((event_id, order_id, provider_payment_id, status))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


async def test_reject_from_new_cancels_without_stock_effect():
    store = FakeReceiptStore(_order("new"), [_ing("flour", "100")])
    result = await RejectReceipt(store).execute("o1")

    assert result.status is OrderStatus.CANCELLED
    assert result.payment_status is PaymentStatus.REJECTED
    assert result.paid_at is None
    assert store.ingredients["flour"].stock_qty == Decimal("100")
    assert store.movements == []
    assert store.status_set == OrderStatus.CANCELLED
    reference, status, paid_at = store.payment_set
    assert reference is None
    assert status == PaymentStatus.REJECTED
    assert paid_at is None
    assert [e[3] for e in store.audit_events] == [PaymentStatus.REJECTED]
    assert store.committed and not store.rolled_back


async def test_reject_from_confirmed_restores_stock():
    store = FakeReceiptStore(_order("confirmed"), [_ing("flour", "100")])
    result = await RejectReceipt(store).execute("o1")

    assert result.status is OrderStatus.CANCELLED
    assert store.ingredients["flour"].stock_qty == Decimal("600")
    assert [(m.reason, m.ingredient_id) for m in store.movements] == [
        ("anulacion", "flour")
    ]
    assert store.committed


async def test_reject_from_preparing_restores_stock():
    store = FakeReceiptStore(_order("preparing"), [_ing("flour", "100")])
    result = await RejectReceipt(store).execute("o1")

    assert result.status is OrderStatus.CANCELLED
    assert store.ingredients["flour"].stock_qty == Decimal("600")
    assert store.committed


async def test_reject_without_receipt_is_not_found():
    store = FakeReceiptStore(_order("new", receipt=False), [_ing("flour", "100")])
    with pytest.raises(ReceiptNotFoundError):
        await RejectReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.status_set is None and store.payment_set is None
    assert store.audit_events == []


async def test_reject_missing_order_is_not_found():
    store = FakeReceiptStore(None, [])
    with pytest.raises(ReceiptNotFoundError):
        await RejectReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed


@pytest.mark.parametrize(
    "payment_status",
    [PaymentStatus.APPROVED, PaymentStatus.REJECTED, PaymentStatus.FAILED],
)
async def test_reject_payment_not_pending(payment_status):
    store = FakeReceiptStore(_order("new", payment_status=payment_status), [])
    with pytest.raises(ReceiptPaymentNotPendingError):
        await RejectReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.payment_set is None


@pytest.mark.parametrize("status", ["pending_delivery", "delivered", "cancelled"])
async def test_reject_order_not_cancellable(status):
    store = FakeReceiptStore(_order(status), [_ing("flour", "100")])
    with pytest.raises(ReceiptOrderNotCancellableError):
        await RejectReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.movements == []


async def test_reject_without_payment_status_yet_is_allowed():
    store = FakeReceiptStore(_order("new", payment_status=None), [])
    result = await RejectReceipt(store).execute("o1")
    assert result.payment_status is PaymentStatus.REJECTED
    assert store.committed


async def test_reject_insufficient_stock_never_blocks():
    store = FakeReceiptStore(_order("confirmed"), [_ing("flour", "0")])
    result = await RejectReceipt(store).execute("o1")
    assert result.status is OrderStatus.CANCELLED
    assert [(m.reason, m.qty_delta, m.ingredient_id) for m in store.movements] == [
        ("anulacion", Decimal("500"), "flour")
    ]


async def test_reject_missing_ingredient_skips_restoration():
    store = FakeReceiptStore(_order("confirmed"), [])
    result = await RejectReceipt(store).execute("o1")
    assert result.status is OrderStatus.CANCELLED
    assert store.movements == []
    assert store.committed


async def test_reject_never_pays():
    store = FakeReceiptStore(_order("preparing"), [_ing("flour", "100")])
    result = await RejectReceipt(store).execute("o1")
    assert result.paid_at is None
    assert not result.paid
    assert result.payment_reference is None

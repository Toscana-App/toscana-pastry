import datetime
from decimal import Decimal

import pytest

from domain.models import Ingredient
from domain.order import Order, OrderItem, PaymentMethod
from domain.order_states import OrderStatus
from domain.orders import OrderItemSnapshot, OrderItemSnapshotLine
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptNotFoundError,
    ReceiptOrderNotReceivableError,
    ReceiptPaymentNotPendingError,
)
from domain.orders import InsufficientOrderStockError
from domain.use_cases.confirm_receipt import ConfirmReceipt


def _ing(id_, stock) -> Ingredient:
    return Ingredient(
        name=id_, unit="g", price_per_unit=Decimal("1"), stock_qty=Decimal(stock), id=id_
    )


def _order(
    status: str = "new",
    payment_status: PaymentStatus | None = PaymentStatus.PENDING,
    receipt: bool = True,
    paid_at: datetime.datetime | None = None,
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
        paid_at=paid_at,
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


async def test_confirm_from_new_deducts_stock_once_and_approves_payment():
    store = FakeReceiptStore(_order("new"), [_ing("flour", "1000")])
    result = await ConfirmReceipt(store).execute("o1")

    assert result.status is OrderStatus.PREPARING
    assert result.payment_status is PaymentStatus.APPROVED
    assert result.paid_at is not None
    assert result.payment_reference == "manual"
    assert store.ingredients["flour"].stock_qty == Decimal("500")
    assert [(m.reason, m.qty_delta, m.ingredient_id) for m in store.movements] == [
        ("pedido", Decimal("-500"), "flour")
    ]
    assert store.status_set == OrderStatus.PREPARING
    reference, status, paid_at = store.payment_set
    assert reference == "manual"
    assert status == PaymentStatus.APPROVED
    assert paid_at is not None
    assert [e[3] for e in store.audit_events] == [PaymentStatus.APPROVED]
    assert store.committed and not store.rolled_back


async def test_confirm_from_confirmed_does_not_deduct_twice():
    store = FakeReceiptStore(_order("confirmed"), [_ing("flour", "100")])
    result = await ConfirmReceipt(store).execute("o1")

    assert result.status is OrderStatus.PREPARING
    assert result.payment_status is PaymentStatus.APPROVED
    assert store.movements == []
    assert store.status_set == OrderStatus.PREPARING
    assert store.committed


async def test_confirm_without_receipt_is_not_found():
    store = FakeReceiptStore(_order("new", receipt=False), [_ing("flour", "1000")])
    with pytest.raises(ReceiptNotFoundError):
        await ConfirmReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.status_set is None and store.payment_set is None
    assert store.audit_events == []


async def test_confirm_missing_order_is_not_found():
    store = FakeReceiptStore(None, [])
    with pytest.raises(ReceiptNotFoundError):
        await ConfirmReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed


@pytest.mark.parametrize(
    "payment_status",
    [PaymentStatus.APPROVED, PaymentStatus.REJECTED, PaymentStatus.FAILED],
)
async def test_confirm_payment_not_pending_rejected(payment_status):
    store = FakeReceiptStore(_order("new", payment_status=payment_status), [])
    with pytest.raises(ReceiptPaymentNotPendingError):
        await ConfirmReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.payment_set is None


@pytest.mark.parametrize("status", ["preparing", "pending_delivery", "delivered", "cancelled"])
async def test_confirm_order_not_receivable(status):
    store = FakeReceiptStore(_order(status), [_ing("flour", "1000")])
    with pytest.raises(ReceiptOrderNotReceivableError):
        await ConfirmReceipt(store).execute("o1")
    assert store.rolled_back and not store.committed
    assert store.movements == []


async def test_confirm_paid_order_is_not_pending():
    paid_at = datetime.datetime(2026, 1, 1, 9, tzinfo=datetime.UTC)
    store = FakeReceiptStore(
        _order("new", payment_status=PaymentStatus.APPROVED, paid_at=paid_at), []
    )
    with pytest.raises(ReceiptPaymentNotPendingError):
        await ConfirmReceipt(store).execute("o1")


async def test_confirm_without_payment_status_yet_is_allowed():
    store = FakeReceiptStore(
        _order("new", payment_status=None), [_ing("flour", "1000")]
    )
    result = await ConfirmReceipt(store).execute("o1")
    assert result.payment_status is PaymentStatus.APPROVED
    assert store.committed


async def test_confirm_insufficient_stock_rolls_back_without_partial_persist():
    store = FakeReceiptStore(_order("new"), [_ing("flour", "200")])
    with pytest.raises(InsufficientOrderStockError) as exc:
        await ConfirmReceipt(store).execute("o1")
    assert exc.value.shortage == {"flour": Decimal("300")}
    assert store.rolled_back and not store.committed
    assert store.movements == []
    assert store.status_set is None
    assert store.payment_set is None
    assert store.audit_events == []

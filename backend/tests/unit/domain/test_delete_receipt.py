import datetime
from decimal import Decimal

import pytest

from domain.order import Order, OrderItem, PaymentMethod
from domain.order_states import OrderStatus
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptNotFoundError,
    ReceiptNotDeletableError,
)
from domain.use_cases.delete_receipt import DeleteReceipt


def _order(
    status=OrderStatus.DELIVERED,
    receipt_file: str | None = "pdf",
    deleted_at: datetime.datetime | None = None,
) -> Order:
    return Order(
        id="o1",
        customer_id="c1",
        code="A1",
        date=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal("1000"),
            )
        ],
        status=status,
        payment_method=PaymentMethod.TRANSFER,
        payment_status=PaymentStatus.APPROVED,
        receipt_file=receipt_file,
        receipt_content_type="application/pdf",
        receipt_size_bytes=1234,
        receipt_uploaded_at=datetime.datetime(2026, 1, 1, 12, tzinfo=datetime.UTC),
        receipt_deleted_at=deleted_at,
    )


class FakeStorageStore:
    def __init__(self):
        self.cleared = None
        self.events = []
        self.committed = False
        self.rolled_back = False

    async def save_receipt(self, *a, **kw):
        pass

    async def mark_receipt_viewed(self, *a, **kw):
        pass

    async def clear_receipt(self, order_id, deleted_at):
        self.cleared = (order_id, deleted_at)

    async def record_payment_event(self, event_id, order_id, provider, status):
        self.events.append((event_id, order_id, provider, status))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


async def test_delete_delivered_order_clears_fields_and_audits():
    store = FakeStorageStore()
    fixed_now = datetime.datetime(2026, 1, 5, 9, tzinfo=datetime.UTC)
    deleted = []
    uc = DeleteReceipt(store, delete_file=lambda order_id, ext: deleted.append((order_id, ext)), now=lambda: fixed_now)
    result = await uc.execute(_order())

    assert deleted == [("o1", "pdf")]
    assert store.cleared == ("o1", fixed_now)
    assert [e[3] for e in store.events] == ["deleted"]
    assert [e[2] for e in store.events] == ["receipt"]
    assert store.committed and not store.rolled_back
    assert result.receipt_file is None
    assert result.receipt_content_type is None
    assert result.receipt_size_bytes is None
    assert result.receipt_uploaded_at is None
    assert result.receipt_deleted_at == fixed_now
    assert result.payment_method == PaymentMethod.TRANSFER
    assert result.status == OrderStatus.DELIVERED


@pytest.mark.parametrize("status", [OrderStatus.NEW, OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.PENDING_DELIVERY])
async def test_delete_non_delivered_order_rejected(status):
    store = FakeStorageStore()
    deleted = []
    uc = DeleteReceipt(store, delete_file=lambda order_id, ext: deleted.append((order_id, ext)), now=lambda: datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC))
    with pytest.raises(ReceiptNotDeletableError):
        await uc.execute(_order(status=status))
    assert deleted == []
    assert store.cleared is None
    assert store.committed is False


async def test_delete_order_without_receipt_raises_not_found():
    store = FakeStorageStore()
    deleted = []
    uc = DeleteReceipt(store, delete_file=lambda order_id, ext: deleted.append((order_id, ext)), now=lambda: datetime.datetime(2026, 1, 5, tzinfo=datetime.UTC))
    with pytest.raises(ReceiptNotFoundError):
        await uc.execute(_order(receipt_file=None))
    assert deleted == []
    assert store.cleared is None


async def test_delete_already_deleted_receipt_raises_not_found():
    store = FakeStorageStore()
    fixed_now = datetime.datetime(2026, 1, 5, 9, tzinfo=datetime.UTC)
    uc = DeleteReceipt(store, delete_file=lambda order_id, ext: None, now=lambda: fixed_now)
    with pytest.raises(ReceiptNotFoundError):
        await uc.execute(_order(deleted_at=fixed_now))
    assert store.cleared is None
    assert store.committed is False
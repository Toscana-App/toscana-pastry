import datetime
from decimal import Decimal

import pytest

from domain.order import Order, OrderItem, PaymentMethod
from domain.order_states import OrderStatus
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptAlreadyUploadedError,
    ReceiptMethodNotTransferError,
    ReceiptOrderTerminalError,
    ReceiptPaymentNotPendingError,
)
from domain.use_cases.upload_receipt import UploadReceipt

_PDF = b"%PDF-1.7 fake"


def _validate(data: bytes) -> str:
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("receipt_too_large")
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG"):
        return "png"
    raise ValueError("receipt_invalid_type")


def _order(
    payment_method=PaymentMethod.TRANSFER,
    payment_status=PaymentStatus.PENDING,
    receipt_file: str | None = None,
    status=OrderStatus.NEW,
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
        payment_method=payment_method,
        payment_status=payment_status,
        receipt_file=receipt_file,
    )


class FakeStorageStore:
    def __init__(self):
        self.saved = None
        self.events = []
        self.committed = False
        self.rolled_back = False

    async def save_receipt(
        self, order_id, *, file, content_type, size_bytes, uploaded_at
    ):
        self.saved = (order_id, file, content_type, size_bytes, uploaded_at)

    async def mark_receipt_viewed(self, order_id, viewed_at):
        pass

    async def clear_receipt(self, order_id, deleted_at):
        pass

    async def record_payment_event(self, event_id, order_id, provider, status):
        self.events.append((event_id, order_id, provider, status))

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _writer(store_files: dict):
    def write(order_id, data, ext):
        store_files[f"{order_id}.{ext}"] = data

    return write


def _deleter(store_files: dict):
    def delete(order_id, ext):
        store_files.pop(f"{order_id}.{ext}", None)

    return delete


async def test_upload_writes_file_and_persists_fields():
    files = {}
    store = FakeStorageStore()
    fixed_now = datetime.datetime(2026, 1, 2, 9, tzinfo=datetime.UTC)
    uc = UploadReceipt(
        store, validate=_validate, write_file=_writer(files), delete_file=_deleter(files), now=lambda: fixed_now
    )
    result = await uc.execute(_order(), _PDF)

    assert files == {"o1.pdf": _PDF}
    assert store.saved == (
        "o1",
        "pdf",
        "application/pdf",
        len(_PDF),
        fixed_now,
    )
    assert [e[3] for e in store.events] == ["uploaded"]
    assert [e[2] for e in store.events] == ["receipt"]
    assert store.committed and not store.rolled_back
    assert result.receipt_file == "pdf"
    assert result.receipt_content_type == "application/pdf"
    assert result.receipt_size_bytes == len(_PDF)
    assert result.receipt_uploaded_at == fixed_now


async def test_upload_cash_order_rejected():
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer({}), delete_file=_deleter({}))
    with pytest.raises(ReceiptMethodNotTransferError):
        await uc.execute(_order(payment_method=PaymentMethod.CASH), _PDF)
    assert store.saved is None and store.committed is False


async def test_upload_existing_receipt_rejected():
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer({}), delete_file=_deleter({}))
    with pytest.raises(ReceiptAlreadyUploadedError):
        await uc.execute(_order(receipt_file="pdf"), _PDF)
    assert store.saved is None


async def test_upload_payment_not_pending_rejected():
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer({}), delete_file=_deleter({}))
    with pytest.raises(ReceiptPaymentNotPendingError):
        await uc.execute(
            _order(payment_status=PaymentStatus.APPROVED), _PDF
        )
    assert store.saved is None


@pytest.mark.parametrize("status", [OrderStatus.DELIVERED, OrderStatus.CANCELLED])
async def test_upload_terminal_order_rejected(status):
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer({}), delete_file=_deleter({}))
    with pytest.raises(ReceiptOrderTerminalError):
        await uc.execute(_order(status=status), _PDF)
    assert store.saved is None


async def test_upload_invalid_type_no_file_written():
    files = {}
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer(files), delete_file=_deleter(files))
    with pytest.raises(ValueError) as exc:
        await uc.execute(_order(), b"GIF89a fake")
    assert str(exc.value) == "receipt_invalid_type"
    assert files == {}
    assert store.saved is None
    assert store.rolled_back and not store.committed


async def test_upload_too_large_no_file_written():
    files = {}
    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer(files), delete_file=_deleter(files))
    with pytest.raises(ValueError) as exc:
        await uc.execute(_order(), b"%PDF-" + b"x" * (5 * 1024 * 1024 + 1))
    assert str(exc.value) == "receipt_too_large"
    assert files == {}
    assert store.rolled_back


async def test_upload_write_failure_rolls_back_and_cleans_file():
    files = {}

    def bad_write(order_id, data, ext):
        files[f"{order_id}.{ext}"] = data
        raise RuntimeError("disk full")

    store = FakeStorageStore()
    uc = UploadReceipt(store, validate=_validate, write_file=bad_write, delete_file=_deleter(files), now=lambda: datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC))
    with pytest.raises(RuntimeError):
        await uc.execute(_order(), _PDF)
    assert files == {}
    assert store.saved is None
    assert store.rolled_back and not store.committed


async def test_upload_persist_failure_cleans_file_and_rolls_back():
    files = {}

    class ExplodingStore(FakeStorageStore):
        async def save_receipt(self, *a, **kw):
            raise RuntimeError("db down")

    store = ExplodingStore()
    uc = UploadReceipt(store, validate=_validate, write_file=_writer(files), delete_file=_deleter(files), now=lambda: datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC))
    with pytest.raises(RuntimeError):
        await uc.execute(_order(), _PDF)
    assert files == {}
    assert store.saved is None
    assert store.rolled_back and not store.committed

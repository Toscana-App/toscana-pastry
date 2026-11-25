import dataclasses
import datetime
import uuid

from domain.order import Order, PaymentMethod
from domain.order_states import OrderStatus
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptAlreadyUploadedError,
    ReceiptMethodNotTransferError,
    ReceiptOrderTerminalError,
    ReceiptPaymentNotPendingError,
)

_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "png": "image/png",
}


class UploadReceipt:
    def __init__(self, store, *, validate, write_file, delete_file, now=None):
        self._store = store
        self._validate = validate
        self._write_file = write_file
        self._delete_file = delete_file
        self._now = now or (lambda: datetime.datetime.now(datetime.UTC))

    async def execute(self, order: Order, data: bytes) -> Order:
        if order.payment_method != PaymentMethod.TRANSFER:
            raise ReceiptMethodNotTransferError()
        if order.receipt_file is not None:
            raise ReceiptAlreadyUploadedError()
        if order.payment_status not in (None, PaymentStatus.PENDING):
            raise ReceiptPaymentNotPendingError()
        if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            raise ReceiptOrderTerminalError()

        ext = None
        try:
            ext = self._validate(data)
            self._write_file(order.id, data, ext)
            uploaded_at = self._now()
            await self._store.save_receipt(
                order.id,
                file=ext,
                content_type=_CONTENT_TYPES[ext],
                size_bytes=len(data),
                uploaded_at=uploaded_at,
            )
            await self._store.record_payment_event(
                str(uuid.uuid4()), order.id, "receipt", "uploaded"
            )
            await self._store.commit()
        except Exception:
            if ext is not None:
                self._delete_file(order.id, ext)
            await self._store.rollback()
            raise
        return dataclasses.replace(
            order,
            receipt_file=ext,
            receipt_content_type=_CONTENT_TYPES[ext],
            receipt_size_bytes=len(data),
            receipt_uploaded_at=uploaded_at,
        )

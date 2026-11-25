import dataclasses
import datetime
import uuid

from domain.order import Order
from domain.order_states import OrderStatus
from domain.receipt import ReceiptNotFoundError, ReceiptNotDeletableError


class DeleteReceipt:
    def __init__(self, store, *, delete_file, now=None):
        self._store = store
        self._delete_file = delete_file
        self._now = now or (lambda: datetime.datetime.now(datetime.UTC))

    async def execute(self, order: Order) -> Order:
        if order.receipt_file is None or order.receipt_deleted_at is not None:
            raise ReceiptNotFoundError()
        if order.status != OrderStatus.DELIVERED:
            raise ReceiptNotDeletableError()

        deleted_at = self._now()
        try:
            self._delete_file(order.id, order.receipt_file)
            await self._store.clear_receipt(order.id, deleted_at)
            await self._store.record_payment_event(
                str(uuid.uuid4()), order.id, "receipt", "deleted"
            )
            await self._store.commit()
        except Exception:
            await self._store.rollback()
            raise
        return dataclasses.replace(
            order,
            receipt_file=None,
            receipt_content_type=None,
            receipt_size_bytes=None,
            receipt_uploaded_at=None,
            receipt_deleted_at=deleted_at,
        )

import uuid

from domain.order import Order
from domain.order_states import OrderStatus, transition
from domain.payment_states import PaymentStatus
from domain.receipt import (
    ReceiptNotFoundError,
    ReceiptOrderNotReceivableError,
    ReceiptPaymentNotPendingError,
)
from domain.repositories import ReceiptVerificationStore
from domain.use_cases.order_stock_effects import deduct_order_stock


class ConfirmReceipt:
    """O5/S4 — Confirmar comprobante: pago pending -> approved + pedido a preparing.

    Cadena de transiciones (todas revalidadas bajo lock):
      - new:       new -> confirmed -> preparing   (deduce stock una sola vez)
      - confirmed: confirmed -> preparing          (stock ya deducido en O1)
    El pago queda approved con referencia "manual" y paid_at; se audita
    en payment_events.
    """

    def __init__(self, store: ReceiptVerificationStore):
        self._store = store

    async def execute(self, order_id: str, *, reference: str = "manual") -> Order:
        store = self._store
        try:
            order = await store.lock_order(order_id)
            if order is None or order.receipt_file is None:
                raise ReceiptNotFoundError()
            if order.payment_status not in (None, PaymentStatus.PENDING):
                raise ReceiptPaymentNotPendingError()
            if order.status not in (OrderStatus.NEW, OrderStatus.CONFIRMED):
                raise ReceiptOrderNotReceivableError()

            order.mark_manual_payment(reference)

            if order.status == OrderStatus.NEW:
                order.status = transition(order.status, OrderStatus.CONFIRMED)
                await deduct_order_stock(order, store)
                order.status = transition(order.status, OrderStatus.PREPARING)
            else:
                order.status = transition(order.status, OrderStatus.PREPARING)

            await store.set_status(order.id, order.status)
            await store.set_payment(
                order.id,
                reference=order.payment_reference,
                status=PaymentStatus.APPROVED,
                paid_at=order.paid_at,
            )
            await store.record_payment_event(
                event_id=str(uuid.uuid4()),
                order_id=order.id,
                provider_payment_id="receipt",
                status=PaymentStatus.APPROVED.value,
            )
            await store.commit()
            return order
        except Exception:
            await store.rollback()
            raise

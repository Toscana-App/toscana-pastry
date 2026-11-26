import uuid

from domain.order import Order
from domain.order_states import OrderStatus, transition
from domain.delivery import DeliveryLinkState
from domain.payment_states import PaymentStatus, transition as payment_transition
from domain.receipt import (
    ReceiptNotFoundError,
    ReceiptOrderNotCancellableError,
    ReceiptPaymentNotPendingError,
)
from domain.repositories import DeliveryLinkRepository, ReceiptVerificationStore
from domain.use_cases.order_stock_effects import restore_order_stock


class RejectReceipt:
    """O5/S4 — Rechazar comprobante: pago pending -> rejected + pedido a cancelled.

    Nunca paga. El efecto de stock es el de la maquina de estados (O1):
      - new:       sin efecto (nunca se dedujo)
      - confirmed / preparing: reintegra el plan
    Se audita en payment_events.
    """

    def __init__(
        self,
        store: ReceiptVerificationStore,
        delivery_links: DeliveryLinkRepository,
    ) -> None:
        self._store = store
        self._delivery_links = delivery_links

    async def execute(self, order_id: str) -> Order:
        store = self._store
        try:
            order = await store.lock_order(order_id)
            if order is None or order.receipt_file is None:
                raise ReceiptNotFoundError()
            if order.payment_status not in (None, PaymentStatus.PENDING):
                raise ReceiptPaymentNotPendingError()
            if order.status not in (
                OrderStatus.NEW,
                OrderStatus.CONFIRMED,
                OrderStatus.PREPARING,
            ):
                raise ReceiptOrderNotCancellableError()

            payment_transition(order.payment_status, PaymentStatus.REJECTED)
            order.payment_status = PaymentStatus.REJECTED

            previous_status = order.status
            order.status = transition(order.status, OrderStatus.CANCELLED)
            if previous_status in (OrderStatus.CONFIRMED, OrderStatus.PREPARING):
                await restore_order_stock(order, store)

            await store.set_status(order.id, order.status)
            await store.set_payment(
                order.id,
                reference=None,
                status=PaymentStatus.REJECTED,
                paid_at=None,
            )
            await self._delivery_links.revoke_active(
                order.id, DeliveryLinkState.CANCELLED.value
            )
            await store.record_payment_event(
                event_id=str(uuid.uuid4()),
                order_id=order.id,
                provider_payment_id="receipt",
                status=PaymentStatus.REJECTED.value,
            )
            await store.commit()
            return order
        except Exception:
            await store.rollback()
            raise

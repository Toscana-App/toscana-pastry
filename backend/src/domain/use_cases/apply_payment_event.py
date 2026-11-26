"""Use case: aplicar un evento de pago del provider al pedido.

La decision de transicion vive aqui, con la maquina de estados de pago
(domain/payment_states). El repository solo persiste lo decidido.
Si la transicion no esta permitida, el evento se registra igual
(audit) pero el estado del pedido no cambia — mismo comportamiento
que el guard SQL que reemplaza.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from domain.payment_states import InvalidPaymentTransitionError, transition
from domain.repositories import PaymentEventStore

if TYPE_CHECKING:
    from domain.order import Order


class ApplyPaymentEvent:
    """Aplica un evento de pago (idempotente por event_id)."""

    def __init__(self, store: PaymentEventStore):
        self._store = store

    async def execute(
        self,
        *,
        order: Order,
        event_id: str,
        provider_payment_id: str,
        status: str,
        paid_at: datetime.datetime,
    ) -> bool:
        if await self._store.get_payment_event(event_id):
            return False
        try:
            transition(order.payment_status, status)
        except InvalidPaymentTransitionError:
            return await self._store.record_payment_event(
                event_id=event_id,
                order_id=order.id,
                provider_payment_id=provider_payment_id,
                status=status,
            )
        return await self._store.apply_payment_event(
            event_id=event_id,
            order_id=order.id,
            provider_payment_id=provider_payment_id,
            current=order.payment_status,
            status=status,
            paid_at=paid_at,
        )

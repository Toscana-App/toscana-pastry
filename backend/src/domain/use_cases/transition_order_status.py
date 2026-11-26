import dataclasses

from domain.order_states import (
    InvalidStatusTransitionError,
    OrderStatus,
    transition,
)
from domain.delivery import revocation_reason
from domain.orders import InsufficientOrderStockError, Order
from domain.repositories import DeliveryLinkRepository, OrderTransitionStore
from domain.use_cases.order_stock_effects import deduct_order_stock, restore_order_stock


class TransitionOrderStatus:
    """O1 — Transicion de estado de pedido (solo revalida la maquina bajo lock)."""

    def __init__(
        self, store: OrderTransitionStore, delivery_links: DeliveryLinkRepository
    ) -> None:
        self._store = store
        self._delivery_links = delivery_links

    async def execute(self, order_id: str, target: str) -> Order:
        store = self._store
        try:
            order = await store.lock_order(order_id)
            if order is None:
                raise InvalidStatusTransitionError("inexistente", target)
            transition(order.status, target)

            if target == OrderStatus.CONFIRMED:
                await deduct_order_stock(order, store)
            elif (
                target == OrderStatus.CANCELLED
                and order.status
                in (OrderStatus.CONFIRMED, OrderStatus.PREPARING)
            ):
                # new -> cancelled no tuvo efecto de stock (O5/S4).
                await restore_order_stock(order, store)

            await store.set_status(order.id, target)
            reason = revocation_reason(target)
            if reason is not None:
                await self._delivery_links.revoke_active(order.id, reason)
            await store.commit()
            return dataclasses.replace(order, status=target)
        except (InsufficientOrderStockError, InvalidStatusTransitionError):
            await store.rollback()
            raise
        except Exception:
            await store.rollback()
            raise

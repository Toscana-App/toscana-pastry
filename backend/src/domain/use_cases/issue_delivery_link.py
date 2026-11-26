from __future__ import annotations

from domain.delivery import (
    DeliveryLink,
    DeliveryLinkNotFoundError,
    OrderNotDeliverableError,
    new_delivery_token,
    revocation_reason,
)
from domain.repositories import DeliveryLinkRepository, OrderRepository


class IssueDeliveryLink:

    def __init__(
        self, orders: OrderRepository, links: DeliveryLinkRepository
    ) -> None:
        self._orders = orders
        self._links = links

    async def execute(self, order_id: str) -> DeliveryLink:
        order = await self._orders.get_full(order_id)
        if order is None:
            raise DeliveryLinkNotFoundError()
        if revocation_reason(order.status) is not None:
            raise OrderNotDeliverableError()
        existing = await self._links.active_for_order(order_id)
        if existing is not None:
            return existing
        if await self._links.create(order_id, new_delivery_token()):
            created = await self._links.active_for_order(order_id)
            if created is not None:
                return created
        concurrent = await self._links.active_for_order(order_id)
        if concurrent is None:
            raise DeliveryLinkNotFoundError()
        return concurrent

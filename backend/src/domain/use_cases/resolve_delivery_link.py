from dataclasses import replace

from domain.delivery import (
    DeliveryLinkNotFoundError,
    DeliveryLinkState,
    PublicDeliveryItem,
    PublicDeliveryView,
    normalize_token,
    public_view,
)
from domain.orders import Order
from domain.repositories import DeliveryLinkRepository, OrderRepository


class ResolveDeliveryLink:
    def __init__(self, links: DeliveryLinkRepository, orders: OrderRepository | None = None):
        self._links = links
        self._orders = orders

    async def execute(self, token: str) -> PublicDeliveryView:
        normalized = normalize_token(token)
        if normalized is None:
            raise DeliveryLinkNotFoundError()
        link = await self._links.find_by_token(normalized)
        if link is None:
            raise DeliveryLinkNotFoundError()
        view = public_view(link)
        if view.state is DeliveryLinkState.EXPIRED or self._orders is None:
            return view
        order: Order | None = await self._orders.get_full(link.order_id)
        if order is None:
            return view
        items = tuple(
            PublicDeliveryItem(name=item.product_name, quantity=item.qty)
            for item in order.items
        )
        return replace(view, items=items)

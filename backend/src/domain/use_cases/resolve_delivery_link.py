from __future__ import annotations

from domain.delivery import (
    DeliveryLinkNotFoundError,
    PublicDeliveryView,
    normalize_token,
    public_view,
)
from domain.repositories import DeliveryLinkRepository


class ResolveDeliveryLink:

    def __init__(self, links: DeliveryLinkRepository) -> None:
        self._links = links

    async def execute(self, token: str) -> PublicDeliveryView:
        normalized = normalize_token(token)
        if normalized is None:
            raise DeliveryLinkNotFoundError()
        link = await self._links.find_by_token(normalized)
        if link is None:
            raise DeliveryLinkNotFoundError()
        return public_view(link)

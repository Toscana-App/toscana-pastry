from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from domain.order_states import ORDER_STATUS_LABELS, OrderStatus


class DeliveryLinkState(StrEnum):
    ACTIVE = "active"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


DELIVERY_STATE_MESSAGES: dict[DeliveryLinkState, str] = {
    DeliveryLinkState.ACTIVE: "Su pedido está en curso",
    DeliveryLinkState.DELIVERED: "Su pedido ha sido entregado",
    DeliveryLinkState.CANCELLED: "Su pedido fue cancelado",
    DeliveryLinkState.EXPIRED: "Este enlace ya no está disponible",
}


class DeliveryLinkError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DeliveryLinkNotFoundError(DeliveryLinkError):
    def __init__(self) -> None:
        super().__init__("delivery_link_not_found")


class OrderNotDeliverableError(DeliveryLinkError):
    def __init__(self) -> None:
        super().__init__("order_not_deliverable")


@dataclass(frozen=True)
class DeliveryLink:
    token: str
    order_id: str
    order_code: str
    order_status: str
    created_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True)
class PublicDeliveryView:
    state: DeliveryLinkState
    order_code: str
    status: str
    status_label: str
    message: str


def new_delivery_token() -> str:
    return str(uuid.uuid4())


def normalize_token(raw: str) -> str | None:
    try:
        parsed = uuid.UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return None
    if parsed.version != 4:
        return None
    return str(parsed)


def revocation_reason(status: str) -> str | None:
    try:
        order_status = OrderStatus(status)
    except ValueError:
        return None
    if order_status is OrderStatus.DELIVERED:
        return DeliveryLinkState.DELIVERED.value
    if order_status is OrderStatus.CANCELLED:
        return DeliveryLinkState.CANCELLED.value
    return None


def state_for_link(link: DeliveryLink) -> DeliveryLinkState:
    reason = revocation_reason(link.order_status)
    if reason is not None:
        return DeliveryLinkState(reason)
    if not link.active:
        return DeliveryLinkState.EXPIRED
    return DeliveryLinkState.ACTIVE


def public_view(link: DeliveryLink) -> PublicDeliveryView:
    state = state_for_link(link)
    visible = state is not DeliveryLinkState.EXPIRED
    return PublicDeliveryView(
        state=state,
        order_code=link.order_code if visible else "",
        status=link.order_status if visible else "",
        status_label=ORDER_STATUS_LABELS.get(link.order_status, "") if visible else "",
        message=DELIVERY_STATE_MESSAGES[state],
    )


def delivery_url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/entrega/{token}"

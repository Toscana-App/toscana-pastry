from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.v1.delivery.dependencies import get_delivery_link_repository
from api.v1.delivery.qr import QR_MEDIA_TYPE, QrUnavailableError, delivery_qr_svg
from api.v1.delivery.schemas import DeliveryLinkResponse, PublicDeliveryResponse
from api.v1.dependencies import require_admin
from api.v1.orders.dependencies import get_order_repository
from api.v1.rate_limit import SlidingWindowRateLimiter
from core.config import settings as app_settings
from data.repositories.sql_delivery_link_repository import SQLDeliveryLinkRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.delivery import (
    DeliveryLink,
    DeliveryLinkError,
    OrderNotDeliverableError,
    delivery_url,
    state_for_link,
)
from domain.models import User
from domain.use_cases.issue_delivery_link import IssueDeliveryLink
from domain.use_cases.resolve_delivery_link import ResolveDeliveryLink

router = APIRouter(prefix="/orders", tags=["delivery"])
public_router = APIRouter(prefix="/public/orders", tags=["delivery"])

public_delivery_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)

_NOT_FOUND_ORDER = "Pedido no encontrado"
_NOT_FOUND_LINK = "Link inválido o expirado"

_PUBLIC_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex",
}

_QR_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
}


def _http_error(exc: DeliveryLinkError, not_found_detail: str) -> HTTPException:
    if isinstance(exc, OrderNotDeliverableError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.code)
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)


def _public_url(link: DeliveryLink) -> str:
    return delivery_url(app_settings.PUBLIC_APP_URL, link.token)


async def _issue_link(
    order_id: str,
    orders: SQLOrderRepository,
    links: SQLDeliveryLinkRepository,
) -> DeliveryLink:
    try:
        return await IssueDeliveryLink(orders, links).execute(order_id)
    except DeliveryLinkError as exc:
        raise _http_error(exc, _NOT_FOUND_ORDER)


@router.get("/{order_id}/delivery-link", response_model=DeliveryLinkResponse)
async def get_delivery_link(
    order_id: str,
    orders: SQLOrderRepository = Depends(get_order_repository),
    links: SQLDeliveryLinkRepository = Depends(get_delivery_link_repository),
    _admin: User = Depends(require_admin),
):
    link = await _issue_link(order_id, orders, links)
    return DeliveryLinkResponse(
        token=link.token,
        url=_public_url(link),
        state=state_for_link(link).value,
        created_at=link.created_at,
    )


@router.get("/{order_id}/delivery-qr.svg")
async def get_delivery_qr(
    order_id: str,
    orders: SQLOrderRepository = Depends(get_order_repository),
    links: SQLDeliveryLinkRepository = Depends(get_delivery_link_repository),
    _admin: User = Depends(require_admin),
):
    link = await _issue_link(order_id, orders, links)
    try:
        svg = delivery_qr_svg(_public_url(link))
    except QrUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="qr_unavailable"
        )
    return Response(
        content=svg,
        media_type=QR_MEDIA_TYPE,
        headers={
            **_QR_HEADERS,
            "Content-Disposition": f'inline; filename="entrega-{link.order_code}.svg"',
        },
    )


@public_router.get(
    "/{token}",
    response_model=PublicDeliveryResponse,
    dependencies=[Depends(public_delivery_limiter.dependency())],
)
async def resolve_public_delivery(
    token: str,
    response: Response,
    links: SQLDeliveryLinkRepository = Depends(get_delivery_link_repository),
):
    try:
        view = await ResolveDeliveryLink(links).execute(token)
    except DeliveryLinkError as exc:
        raise _http_error(exc, _NOT_FOUND_LINK)
    response.headers.update(_PUBLIC_HEADERS)
    return PublicDeliveryResponse(
        state=view.state.value,
        order_code=view.order_code,
        status=view.status,
        status_label=view.status_label,
        message=view.message,
    )

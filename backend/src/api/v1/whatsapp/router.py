"""Router de WhatsApp Business (RF-P10-07/08, C7).

Owner-only:
- GET /whatsapp/sends — listado con estados (?status, ?from, ?to, paginado)
- GET /whatsapp/sends/stats — métricas 30 dias (read_rate)
- POST /whatsapp/sends/{id}/resend — reintenta un fallido de business_api
  (409 si no es reintenable; 429 si supera el budget RNF-P10-06)
Namespace: /api/v1/whatsapp.
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.v1.dependencies import require_admin
from api.v1.whatsapp.dependencies import (
    get_whatsapp_provider,
    get_whatsapp_send_repository,
)
from api.v1.whatsapp.schemas import (
    ResendResponse,
    SendListResponse,
    SendResponse,
    SendStatsResponse,
)
from data.repositories.sql_whatsapp_send_repository import (
    SQLWhatsAppSendRepository,
)
from domain.models import User
from domain.whatsapp_provider import WhatsAppProvider
from domain.whatsapp_send import (
    BUSINESS_API_DAILY_LIMIT,
    WhatsAppSend,
    can_resend,
    read_rate,
    reset_for_resend,
)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

STATS_WINDOW_DAYS = 30


def _response(send: WhatsAppSend) -> SendResponse:
    return SendResponse(
        id=send.id,
        provider=send.provider,
        status=send.status,
        reference_kind=send.reference_kind,
        reference_id=send.reference_id,
        sent_at=send.sent_at,
        message_id=send.message_id,
        failed_reason=send.failed_reason,
        delivered_at=send.delivered_at,
        read_at=send.read_at,
    )


@router.get("/sends", response_model=SendListResponse)
async def list_sends(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(sent|delivered|read|failed)$",
    ),
    from_: datetime.datetime | None = Query(default=None, alias="from"),
    to: datetime.datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    repo: SQLWhatsAppSendRepository = Depends(get_whatsapp_send_repository),
    _admin: User = Depends(require_admin),
) -> SendListResponse:
    """GET /whatsapp/sends: envios con estados (solo el owner)."""
    items, total = await repo.list(
        status=status_filter,
        from_=from_,
        to=to,
        page=page,
        page_size=page_size,
    )
    return SendListResponse(
        items=[_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sends/stats", response_model=SendStatsResponse)
async def sends_stats(
    repo: SQLWhatsAppSendRepository = Depends(get_whatsapp_send_repository),
    _admin: User = Depends(require_admin),
) -> SendStatsResponse:
    """GET /whatsapp/sends/stats: métricas de la ultima ventana (30 dias)."""
    counts = await repo.stats(window_days=STATS_WINDOW_DAYS)
    return SendStatsResponse(
        total=counts["total"],
        sent=counts["sent"],
        delivered=counts["delivered"],
        read=counts["read"],
        failed=counts["failed"],
        read_rate=read_rate(counts["total"], counts["read"]),
    )


@router.post("/sends/{send_id}/resend", response_model=ResendResponse)
async def resend_send(
    send_id: str,
    repo: SQLWhatsAppSendRepository = Depends(get_whatsapp_send_repository),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
    _admin: User = Depends(require_admin),
) -> ResendResponse:
    """POST /whatsapp/sends/{id}/resend: reintenta un envio fallido.

    Solo `status=failed` + `provider=business_api` (409 en caso contrario).
    Cuenta contra el budget diario RNF-P10-06 (429 con dia sugerido).
    """
    send = await repo.get(send_id)
    if send is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Send not found",
        )
    if not can_resend(send):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden reintentar envios fallidos por business_api",
        )

    now = datetime.datetime.now(datetime.UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = await repo.count_provider_since(
        provider="business_api", since=today_start
    )
    if used_today >= BUSINESS_API_DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "whatsapp_budget_exceeded",
                "limit": BUSINESS_API_DAILY_LIMIT,
                "retry_after": (
                    (today_start + datetime.timedelta(days=1)).date().isoformat()
                ),
            },
        )

    result = await provider.send(send.phone, send.message)
    updated = reset_for_resend(
        send,
        new_message_id=result.message_id or send.id,
        now=now,
    )
    await repo.update(updated)
    return ResendResponse(send=_response(updated))

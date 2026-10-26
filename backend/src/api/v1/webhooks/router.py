"""Webhook router for Mercado Pago (C1.6).

Namespace: /api/v1/webhooks.
"""

from __future__ import annotations

import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.requests import Request

from api.v1.orders.dependencies import get_order_repository
from api.v1.orders.schemas import WebhookResponse
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.mock_checkout_provider import MockCheckoutProvider
from domain.order import PaymentMethod, PaymentStatus

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercadopago", response_model=WebhookResponse)
async def mercadopago_webhook(
    request: Request,
    repo: SQLOrderRepository = Depends(get_order_repository),
):
    """POST /webhooks/mercadopago: webhook de pago (firma + idempotencia).

    Público (solo firma, sin auth por cookie).
    """
    raw = await request.body()
    signature = request.headers.get("x-signature")

    provider = MockCheckoutProvider()
    verified = provider.verify_webhook(raw, signature)
    if verified is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        ) from None

    # Parse payload
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid payload",
        ) from err

    # Extract payment info
    payment_id = payload.get("id", "")
    payment_status_str = payload.get("status", "")
    order_id = payload.get("resource", "")

    # Map status
    status_map = {
        "approved": PaymentStatus.APPROVED,
        "rejected": PaymentStatus.REJECTED,
        "failed": PaymentStatus.FAILED,
        "pending": PaymentStatus.PENDING,
    }
    payment_status = status_map.get(payment_status_str)
    if payment_status is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid status",
        )

    # Dedupe check
    if await repo.get_payment_event(payment_id):
        return WebhookResponse()

    # Apply status
    order = await repo.get(order_id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    # Cash orders: ignore MP webhook (payment_status stays None, paid stays false)
    if order.payment_method == PaymentMethod.CASH:
        # Still record the event for dedupe idempotency
        await repo.record_payment_event(
            event_id=f"evt_{payment_id}",
            order_id=order_id,
            provider_payment_id=payment_id,
            status=payment_status,
        )
        return WebhookResponse()

    # approved → paid (monotonic guard; skip if already paid)
    if payment_status == PaymentStatus.APPROVED and not order.paid:
        await repo.update_payment_status(
            order_id=order_id,
            reference=payment_id,
            status=payment_status,
            paid_at=datetime.datetime.now(datetime.UTC),
        )
    elif payment_status in (
        PaymentStatus.PENDING,
        PaymentStatus.REJECTED,
        PaymentStatus.FAILED,
    ):
        # pending/rejected/failed: never overwrite a terminal approved state
        if order.payment_status == PaymentStatus.APPROVED:
            # Already approved — skip non-terminal updates (dedupe still recorded above)
            await repo.record_payment_event(
                event_id=f"evt_{payment_id}",
                order_id=order_id,
                provider_payment_id=payment_id,
                status=payment_status,
            )
            return WebhookResponse()
        await repo.update_payment_status(
            order_id=order_id,
            reference=payment_id,
            status=payment_status,
            paid_at=order.paid_at,
        )

    # Record event (idempotent)
    await repo.record_payment_event(
        event_id=f"evt_{payment_id}",
        order_id=order_id,
        provider_payment_id=payment_id,
        status=payment_status,
    )

    return WebhookResponse()

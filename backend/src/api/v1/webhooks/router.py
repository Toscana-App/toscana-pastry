"""Webhook router for Mercado Pago (C1.6).

Namespace: /api/v1/webhooks.
"""

from __future__ import annotations

import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.requests import Request

from api.v1.orders.dependencies import get_checkout_provider, get_order_repository
from api.v1.orders.schemas import WebhookResponse
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.checkout_provider import CheckoutProvider, PaymentProviderError
from domain.order import PaymentMethod, PaymentStatus

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercadopago", response_model=WebhookResponse)
async def mercadopago_webhook(
    request: Request,
    repo: SQLOrderRepository = Depends(get_order_repository),
    provider: CheckoutProvider = Depends(get_checkout_provider),
):
    """POST /webhooks/mercadopago: notificación de pago (firma + idempotencia).

    Público (solo firma, sin auth por cookie). El body solo trae el id del
    pago; el estado y el pedido (external_reference) se leen del proveedor.
    """
    verified = provider.verify_webhook(
        await request.body(),
        request.headers.get("x-signature"),
        request.headers.get("x-request-id"),
    )
    if verified is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    payload = json.loads(verified)
    if payload.get("type") != "payment":
        return WebhookResponse()

    payment_id = str(payload["data"]["id"])
    try:
        payment = await provider.get_payment(payment_id)
    except PaymentProviderError as err:
        # Non-200 makes Mercado Pago retry the notification later.
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="payment_provider_error",
        ) from err

    if not payment.order_id:
        return WebhookResponse()
    payment_status = PaymentStatus(payment.status)

    # Dedupe by (payment, status): one payment is notified once per status.
    event_id = f"{payment_id}:{payment_status.value}"
    if await repo.get_payment_event(event_id):
        return WebhookResponse()

    order = await repo.get(payment.order_id)
    if order is None:
        return WebhookResponse()

    # Cash orders ignore MP webhooks (payment_status stays None, paid false).
    if order.payment_method != PaymentMethod.CASH:
        if payment_status == PaymentStatus.APPROVED:
            # Monotonic guard: approved is applied at most once.
            if not order.paid:
                await repo.update_payment_status(
                    order_id=order.id,
                    reference=payment_id,
                    status=payment_status,
                    paid_at=datetime.datetime.now(datetime.UTC),
                )
        elif order.payment_status != PaymentStatus.APPROVED:
            # pending/rejected/failed never overwrite a terminal approved.
            await repo.update_payment_status(
                order_id=order.id,
                reference=payment_id,
                status=payment_status,
                paid_at=order.paid_at,
            )

    await repo.record_payment_event(
        event_id=event_id,
        order_id=order.id,
        provider_payment_id=payment_id,
        status=payment_status,
    )
    return WebhookResponse()


from __future__ import annotations

import datetime
import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.requests import Request
from pydantic import ValidationError

from api.v1.orders.dependencies import get_checkout_provider, get_order_repository
from api.v1.orders.schemas import WebhookNotification, WebhookResponse
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.checkout_provider import CheckoutProvider, PaymentProviderError
from domain.order import PaymentStatus

_PAYMENT_CURRENCY = "ARS"

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/mercadopago", response_model=WebhookResponse)
async def mercadopago_webhook(
    request: Request,
    repo: SQLOrderRepository = Depends(get_order_repository),
    provider: CheckoutProvider = Depends(get_checkout_provider),
):
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

    try:
        notification = WebhookNotification.model_validate(json.loads(verified))
    except (ValidationError, ValueError) as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_webhook_payload",
        ) from err
    if notification.type != "payment":
        return WebhookResponse()

    payment_id = str(notification.data.id).strip() if notification.data else ""
    if not payment_id:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_webhook_payload",
        )
    try:
        payment = await provider.get_payment(payment_id)
    except PaymentProviderError as err:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="payment_provider_error",
        ) from err

    if not payment.order_id:
        return WebhookResponse()
    payment_status = PaymentStatus(payment.status)

    event_id = f"{payment_id}:{payment_status.value}"
    if await repo.get_payment_event(event_id):
        return WebhookResponse()

    order = await repo.get(payment.order_id)
    if order is None:
        logger.warning(
            "mercadopago webhook for unknown order %s (payment %s)",
            payment.order_id,
            payment_id,
        )
        return WebhookResponse()

    if payment_status == PaymentStatus.APPROVED:
        expected = order.total - (order.discount_amount or Decimal("0"))
        if payment.amount != expected or payment.currency != _PAYMENT_CURRENCY:
            logger.error(
                "mercadopago payment %s discrepancy for order %s: "
                "amount %s %s, expected %s %s; not marked paid",
                payment_id,
                order.id,
                payment.amount,
                payment.currency,
                expected,
                _PAYMENT_CURRENCY,
            )
            return WebhookResponse()

    await repo.apply_payment_event(
        event_id=event_id,
        order_id=order.id,
        provider_payment_id=payment_id,
        status=payment_status,
        paid_at=datetime.datetime.now(datetime.UTC),
    )
    return WebhookResponse()

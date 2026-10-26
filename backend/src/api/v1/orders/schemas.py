"""Order API schemas (C1.0/C1.4/C1.5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PaidResponse(BaseModel):
    """Response from PATCH /orders/{id}/paid."""

    paid: bool


class PaymentInitResponse(BaseModel):
    """Response from POST /orders/{id}/payment."""

    reference: str
    checkout_url: str


class PaymentStatusResponse(BaseModel):
    """Response from GET /orders/{id}/payment."""

    status: str | None
    paid: bool
    payment_reference: str | None = None
    updated_at: datetime | None = None


class WebhookResponse(BaseModel):
    """Response from POST /webhooks/mercadopago."""

    ok: bool = True

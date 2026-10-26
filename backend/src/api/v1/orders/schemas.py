"""Order + Lead API schemas (C1.0/C1.4/C1.5 / C6 / RF-P11-13, C5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


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


# ─── C6 Portal schemas ──────────────────────────────────────────────


class OrderItemSchema(BaseModel):
    """Order line item (read)."""

    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    portion_note: str = ""
    total: Decimal


class OrderDetailSchema(BaseModel):
    """Order detail for portal "mis pedidos" (RF-P11-08)."""

    id: str
    code: str
    customer_id: str
    status: str
    date: datetime
    payment_method: str
    delivery_mode: str
    delivery_address: str | None = None
    coupon_code: str | None = None
    discount_amount: Decimal | None = None
    paid: bool
    payment_status: str | None = None
    total: Decimal
    items: list[OrderItemSchema]
    created_at: datetime


class OrderListSchema(BaseModel):
    """Paginated order list for portal."""

    orders: list[OrderDetailSchema]
    total: int
    page: int
    page_size: int


class PortalOrderCreateRequest(BaseModel):
    """Request body for POST /orders (portal creation, C6)."""

    items: list[dict[str, Any]] = Field(..., min_length=1)
    date: datetime
    delivery_mode: str = "delivery"
    delivery_address: str | None = None
    payment_method: str = "cash"
    coupon_code: str | None = None


class OrderWindowResponse(BaseModel):
    """Response for order window status."""

    open: bool
    reopens_at: datetime | None = None
    message: str = ""

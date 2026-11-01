"""Schemas Pydantic de la API de pedidos (Fase 6, P6).

Reglas del contrato:
- Money viaja como long de centavos (int) en el wire (RF-P5-01/04); el
  dominio trabaja en Decimal y la conversion vive en el borde (money.py).
- `margin_pct` es Pct (0-100, string decimal): override por pedido
  (mismo rango que el motor), null = margen del tenant.
- `qty`/`available`/`required` son Qty (cantidades, no dinero).
- El desglose de cada item es el SNAPSHOT congelado al crear el pedido
  (RNF-P6-03): las responses nunca recalculan contra el catalogo.
- `date` es la fecha del pedido (entrega/produccion), elegible libremente.
"""
from __future__ import annotations

import datetime as dt
from typing import List, Literal, Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


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
    updated_at: dt.datetime | None = None


class WebhookResponse(BaseModel):
    """Response from POST /webhooks/mercadopago."""

    ok: bool = True


class WebhookNotificationData(BaseModel):
    """``data`` object of a Mercado Pago notification."""

    id: str | int = Field(..., description="Provider payment id")


class WebhookNotification(BaseModel):
    """Mercado Pago notification body (validated after the signature)."""

    type: str | None = None
    data: WebhookNotificationData | None = None


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
    date: dt.datetime
    payment_method: str
    delivery_mode: str
    delivery_address: str | None = None
    coupon_code: str | None = None
    discount_amount: Decimal | None = None
    paid: bool
    payment_status: str | None = None
    total: Decimal
    items: list[OrderItemSchema]
    created_at: dt.datetime


class OrderListSchema(BaseModel):
    """Paginated order list for portal."""

    orders: list[OrderDetailSchema]
    total: int
    page: int
    page_size: int


class PortalOrderItemRequest(BaseModel):
    """Portal order line: price and name are resolved server-side."""

    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    portion_note: str = ""


class PortalOrderCreateRequest(BaseModel):
    """Request body for POST /orders (portal creation, C6)."""

    items: list[PortalOrderItemRequest] = Field(..., min_length=1)
    date: dt.datetime
    delivery_mode: str = "delivery"
    delivery_address: str | None = None
    payment_method: str = "cash"
    coupon_code: str | None = None


class OrderWindowResponse(BaseModel):
    """Response for order window status."""

    open: bool
    reopens_at: dt.datetime | None = None
    message: str = ""


from api.v1.money import Money, Pct, Qty

OrderStatus = Literal["nuevo", "confirmado", "entregado", "cancelado"]


class OrderItemInput(BaseModel):
    """Linea del pedido. `portions` omitido = porciones del producto
    (el factor de escalado se vuelve 1)."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=36)
    qty: int = Field(ge=1)
    portions: Optional[int] = Field(default=None, ge=1, le=999)
    note: str = Field(default="", max_length=200)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(min_length=1, max_length=36)
    date: dt.date
    margin_pct: Optional[Pct] = None
    items: List[OrderItemInput] = Field(min_length=1)


class OrderUpdate(BaseModel):
    """PATCH /orders/{id}: parcial. Solo pedidos en estado `nuevo`."""

    model_config = ConfigDict(extra="forbid")

    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    date: Optional[dt.date] = None
    margin_pct: Optional[Pct] = None
    items: Optional[List[OrderItemInput]] = Field(default=None, min_length=1)


class OrderStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderPreviewRequest(BaseModel):
    """Cotizacion en vivo del wizard (admin): items + margin, sin
    persistir. Mismo calculo que el create."""

    model_config = ConfigDict(extra="forbid")

    margin_pct: Optional[Pct] = None
    items: List[OrderItemInput] = Field(min_length=1)


class SnapshotLineResponse(BaseModel):
    ingredient_id: str
    ingredient_name: str
    qty: Qty
    unit: str
    cost: Money
    is_missing: bool = False


class OrderItemBreakdown(BaseModel):
    """Desglose del motor congelado en el snapshot (RNF-P6-03)."""

    materials: Money
    waste: Money
    materials_con_merma: Money
    labor: Money
    gas: Money
    base: Money
    margin_pct: Pct
    final: Money
    rounded: Money


class OrderItemResponse(BaseModel):
    product_id: str
    product_name: str
    qty: int
    portions: int
    note: str
    complete: bool
    missing_ingredients: List[str]
    price: OrderItemBreakdown
    lines: List[SnapshotLineResponse]
    rounded: Money


class OrderCustomerResponse(BaseModel):
    id: str
    name: str
    phone: str


class OrderListItem(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    date: dt.date
    status: OrderStatus
    item_count: int
    total: Money
    created_at: str


class OrderListResponse(BaseModel):
    items: List[OrderListItem]
    total: int
    page: int
    page_size: int


class OrderDetailResponse(BaseModel):
    id: str
    customer: OrderCustomerResponse
    date: dt.date
    status: OrderStatus
    margin_pct: Optional[Pct] = None
    items: List[OrderItemResponse]
    total: Money
    whatsapp_sent_at: Optional[str] = None
    created_at: str
    updated_at: str


class OrderPreviewItemResponse(BaseModel):
    product_id: str
    product_name: str
    qty: int
    portions: int
    complete: bool
    missing_ingredients: List[str]
    price: OrderItemBreakdown
    lines: List[SnapshotLineResponse]
    rounded: Money


class OrderPreviewResponse(BaseModel):
    margin_pct: Pct  # aplicado (override o tenant)
    tenant_margin_pct: Pct
    items: List[OrderPreviewItemResponse]
    total: Money


class InsufficientStockItem(BaseModel):
    ingredient_id: str
    ingredient_name: str
    available: Qty
    required: Qty


class InsufficientStockResponse(BaseModel):
    """409 al confirmar: stock insuficiente. Nada se descuenta (RNF-P6-04)."""

    insufficient_stock: List[InsufficientStockItem]


class WhatsAppLinkResponse(BaseModel):
    url: str
    message: str

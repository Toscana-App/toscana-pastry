"""Order + Lead API schemas (C1.0/C1.4/C1.5 / C6 / RF-P11-13, C5) + Fase 6 P6.

P6: money viaja como long de centavos en el wire (RF-P5-01/04); `margin_pct`
es Pct 0-100; `qty`/`available`/`required` son Qty; el desglose de cada item
es el snapshot congelado al crear el pedido (RNF-P6-03)."""

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money, Pct, Qty


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


# ─── Fase 6 P6 schemas ─────────────────────────────────────────────

OrderStatus = Literal["nuevo", "confirmado", "entregado", "cancelado"]


class OrderItemInput(BaseModel):
    """Linea del pedido. `portions` omitido = porciones del producto
    (el factor de escalado se vuelve 1)."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=36)
    qty: int = Field(ge=1)
    portions: int | None = Field(default=None, ge=1, le=999)
    note: str = Field(default="", max_length=200)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(min_length=1, max_length=36)
    date: Date
    margin_pct: Pct | None = None
    items: list[OrderItemInput] = Field(min_length=1)


class OrderUpdate(BaseModel):
    """PATCH /orders/{id}: parcial. Solo pedidos en estado `nuevo`."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = Field(default=None, min_length=1, max_length=36)
    date: Date | None = None
    margin_pct: Pct | None = None
    items: list[OrderItemInput] | None = Field(default=None, min_length=1)


class OrderStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderPreviewRequest(BaseModel):
    """Cotizacion en vivo del wizard (admin): items + margin, sin
    persistir. Mismo calculo que el create."""

    model_config = ConfigDict(extra="forbid")

    margin_pct: Pct | None = None
    items: list[OrderItemInput] = Field(min_length=1)


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
    missing_ingredients: list[str]
    price: OrderItemBreakdown
    lines: list[SnapshotLineResponse]
    rounded: Money


class OrderCustomerResponse(BaseModel):
    id: str
    name: str
    phone: str


class OrderListItem(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    date: Date
    status: OrderStatus
    item_count: int
    total: Money
    created_at: str


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int


class OrderDetailResponse(BaseModel):
    id: str
    customer: OrderCustomerResponse
    date: Date
    status: OrderStatus
    margin_pct: Pct | None = None
    items: list[OrderItemResponse]
    total: Money
    whatsapp_sent_at: str | None = None
    created_at: str
    updated_at: str


class OrderPreviewItemResponse(BaseModel):
    product_id: str
    product_name: str
    qty: int
    portions: int
    complete: bool
    missing_ingredients: list[str]
    price: OrderItemBreakdown
    lines: list[SnapshotLineResponse]
    rounded: Money


class OrderPreviewResponse(BaseModel):
    margin_pct: Pct  # aplicado (override o tenant)
    tenant_margin_pct: Pct
    items: list[OrderPreviewItemResponse]
    total: Money


class InsufficientStockItem(BaseModel):
    ingredient_id: str
    ingredient_name: str
    available: Qty
    required: Qty


class InsufficientStockResponse(BaseModel):
    """409 al confirmar: stock insuficiente. Nada se descuenta (RNF-P6-04)."""

    insufficient_stock: list[InsufficientStockItem]


class WhatsAppLinkResponse(BaseModel):
    url: str
    message: str

from __future__ import annotations

import datetime as dt
from typing import List, Literal, Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class PaidResponse(BaseModel):

    paid: bool


class PaymentInitResponse(BaseModel):

    reference: str
    checkout_url: str


class PaymentStatusResponse(BaseModel):

    status: str | None
    paid: bool
    payment_reference: str | None = None
    updated_at: dt.datetime | None = None


class WebhookResponse(BaseModel):

    ok: bool = True


class WebhookNotificationData(BaseModel):

    id: str | int = Field(..., description="Provider payment id")


class WebhookNotification(BaseModel):

    type: str | None = None
    data: WebhookNotificationData | None = None




class OrderItemSchema(BaseModel):

    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    portion_note: str = ""
    total: Decimal


class OrderDetailSchema(BaseModel):

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

    orders: list[OrderDetailSchema]
    total: int
    page: int
    page_size: int


class PortalOrderItemRequest(BaseModel):

    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    portion_note: str = ""


class PortalOrderCreateRequest(BaseModel):

    items: list[PortalOrderItemRequest] = Field(..., min_length=1)
    date: dt.datetime
    delivery_mode: str = "delivery"
    delivery_address: str | None = None
    payment_method: str = "cash"
    coupon_code: str | None = None


class OrderWindowResponse(BaseModel):

    open: bool
    reopens_at: dt.datetime | None = None
    message: str = ""


from api.v1.money import Money, Pct, Qty

OrderStatus = Literal["nuevo", "confirmado", "entregado", "cancelado"]


class OrderItemInput(BaseModel):

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

    model_config = ConfigDict(extra="forbid")

    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    date: Optional[dt.date] = None
    margin_pct: Optional[Pct] = None
    items: Optional[List[OrderItemInput]] = Field(default=None, min_length=1)


class OrderStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderPreviewRequest(BaseModel):

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
    name: str = ""
    phone: str = ""


class OrderListItem(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    date: dt.date
    status: OrderStatus
    item_count: int
    total: Money
    paid: bool = False
    payment_method: str = "cash"
    created_at: str


class OrderListResponse(BaseModel):
    items: List[OrderListItem]
    total: int
    page: int
    page_size: int


class OrderInvoiceSummary(BaseModel):
    numero: int
    cae: str
    cae_vto: str
    pdf_url: str


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
    invoice: OrderInvoiceSummary | None = None


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
    margin_pct: Pct
    tenant_margin_pct: Pct
    items: List[OrderPreviewItemResponse]
    total: Money


class InsufficientStockItem(BaseModel):
    ingredient_id: str
    ingredient_name: str
    available: Qty
    required: Qty


class InsufficientStockResponse(BaseModel):

    insufficient_stock: List[InsufficientStockItem]


class WhatsAppLinkResponse(BaseModel):
    url: str
    message: str




class WeeklyRange(BaseModel):

    model_config = ConfigDict(populate_by_name=True)

    from_: dt.date = Field(alias="from")
    to: dt.date


class WeeklyItem(BaseModel):

    id: str
    customer: str
    date: dt.date
    items_count: int
    total: Money
    paid: bool
    payment_method: str


class WeeklyTotals(BaseModel):

    amount: Money
    paid: Money
    unpaid: Money


class WeeklySummaryResponse(BaseModel):

    week: WeeklyRange
    items: List[WeeklyItem]
    totals: WeeklyTotals

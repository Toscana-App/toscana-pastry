"""Schemas Pydantic de la API de pedidos (Fase 6, P6).

Reglas del contrato:
- Money viaja como str (RNF-P4-02). `margin_pct` es el override por
  pedido (0-200, mismo rango que el motor): null = margen del tenant.
- El desglose de cada item es el SNAPSHOT congelado al crear el pedido
  (RNF-P6-03): las responses nunca recalculan contra el catalogo.
- `date` es la fecha del pedido (entrega/produccion), elegible libremente.
"""
import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money

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
    date: datetime.date
    margin_pct: Optional[Money] = None
    items: List[OrderItemInput] = Field(min_length=1)


class OrderUpdate(BaseModel):
    """PATCH /orders/{id}: parcial. Solo pedidos en estado `nuevo`."""

    model_config = ConfigDict(extra="forbid")

    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    date: Optional[datetime.date] = None
    margin_pct: Optional[Money] = None
    items: Optional[List[OrderItemInput]] = Field(default=None, min_length=1)


class OrderStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


class OrderPreviewRequest(BaseModel):
    """Cotizacion en vivo del wizard (admin): items + margin, sin
    persistir. Mismo calculo que el create."""

    model_config = ConfigDict(extra="forbid")

    margin_pct: Optional[Money] = None
    items: List[OrderItemInput] = Field(min_length=1)


class SnapshotLineResponse(BaseModel):
    ingredient_id: str
    ingredient_name: str
    qty: Money
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
    margin_pct: Money
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
    date: datetime.date
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
    date: datetime.date
    status: OrderStatus
    margin_pct: Optional[Money] = None
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
    margin_pct: Money  # aplicado (override o tenant)
    tenant_margin_pct: Money
    items: List[OrderPreviewItemResponse]
    total: Money


class InsufficientStockItem(BaseModel):
    ingredient_id: str
    ingredient_name: str
    available: Money
    required: Money


class InsufficientStockResponse(BaseModel):
    """409 al confirmar: stock insuficiente. Nada se descuenta (RNF-P6-04)."""

    insufficient_stock: List[InsufficientStockItem]


class WhatsAppLinkResponse(BaseModel):
    url: str
    message: str

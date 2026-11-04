"""Schemas Pydantic de la API de presupuestos (Fase 7, P7/P8).

Reglas del contrato (api_endpoints.md §F3):
- Money viaja como long de centavos (int) en el wire (RF-P8-03); el
  dominio trabaja en Decimal y la conversion vive en el borde (money.py).
- `margin_pct` es Pct (string decimal), 0-200; null = margen del tenant.
- `calculation_mode`: "cost_plus" (margen sobre costo) o "manual"
  (precio de venta personalizado por item; RF-P7-05/RF-P8).
- El create viene del wizard completo (P7): customer_id resuelto por el
  frontend (POST /customers con 409+X-Customer-Id en duplicados) + items
  + margen + modo.
- La respuesta nunca recalcula contra el catalogo: los totales se derivan
  de los items guardados (borde puro, dominio).
"""
import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.money import Money, Pct, Qty

BudgetStatus = Literal["borrador", "enviado"]
CalculationMode = Literal["cost_plus", "manual"]


class BudgetItemInput(BaseModel):
    """Linea del wizard. `price_override` solo tiene efecto en modo
    manual; en cost_plus debe venir nulo (el backend la ignora)."""

    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=36)
    qty: int = Field(ge=1)
    price_override: Optional[Money] = None


class BudgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(min_length=1, max_length=36)
    calculation_mode: CalculationMode = "cost_plus"
    margin_pct: Optional[Pct] = Field(default=None, ge=0, le=200)
    items: List[BudgetItemInput] = Field(min_length=1)
    delivery_address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("delivery_address")
    @classmethod
    def _strip_address(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BudgetUpdate(BaseModel):
    """PUT /budgets/{id}: parcial. Borrador y enviado (reenviar, RF-P8-05).

    `delivery_address` ausente conserva el snapshot; presente (o null
    explicito) lo reemplaza (RNF-P7-04)."""

    model_config = ConfigDict(extra="forbid")

    customer_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    calculation_mode: Optional[CalculationMode] = None
    margin_pct: Optional[Pct] = Field(default=None, ge=0, le=200)
    items: Optional[List[BudgetItemInput]] = Field(default=None, min_length=1)
    delivery_address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("delivery_address")
    @classmethod
    def _strip_address(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BudgetItemsPatch(BaseModel):
    """PATCH /budgets/{id}/items: reemplaza lineas y recalcula."""

    model_config = ConfigDict(extra="forbid")

    items: List[BudgetItemInput] = Field(min_length=1)


class BudgetItemResponse(BaseModel):
    product_id: str
    product_name: str
    qty: int
    unit_cost: Money
    unit_selling: Money
    line_cost: Money
    line_selling: Money
    price_overridden: bool = False


class BudgetSummary(BaseModel):
    subtotal: Money
    total_costos: Money
    ganancia: Money
    total_venta: Money


class BudgetCustomerResponse(BaseModel):
    id: str
    name: str
    phone: str


class BudgetListItem(BaseModel):
    id: str
    seq: str
    customer_name: str
    customer_phone: str
    status: BudgetStatus
    item_count: int
    total: Money  # subtotal (sin IVA)
    version: int
    created_at: str
    sent_at: Optional[str] = None


class BudgetListResponse(BaseModel):
    items: List[BudgetListItem]
    total: int
    page: int
    page_size: int


class BudgetDetailResponse(BaseModel):
    id: str
    seq: str
    customer: BudgetCustomerResponse
    delivery_address: Optional[str] = None
    status: BudgetStatus
    calculation_mode: CalculationMode
    margin_pct: Optional[Pct] = None
    version: int
    items: List[BudgetItemResponse]
    summary: BudgetSummary
    created_at: str
    updated_at: str
    sent_at: Optional[str] = None


class RecalculateResponse(BaseModel):
    summary: BudgetSummary
    margin_applied: Pct  # override o tenant (el que se uso)


class ConvertToOrderResponse(BaseModel):
    order_id: str
    seq: str  # del presupuesto, para el log del frontend


class WhatsAppLinkResponse(BaseModel):
    """POST /budgets/{id}/whatsapp-link (P10): link wa.me prellenado.

    `sent_at` es el momento del registro de auditoría (RF-P10-02)."""

    url: str
    sent_at: str  # ISO 8601 UTC

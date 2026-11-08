from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.money import Money, Pct

BudgetStatus = Literal["borrador", "enviado"]
CalculationMode = Literal["cost_plus", "manual"]


class BudgetItemInput(BaseModel):

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
    iva: Money
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
    total: Money
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
    margin_applied: Pct


class ConvertToOrderResponse(BaseModel):
    order_id: str
    seq: str


class WhatsAppLinkResponse(BaseModel):

    url: str
    sent_at: str

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from api.v1.money import Money

Audience = Literal["revendedores", "consumidor_final"]


class PreviewLineItem(BaseModel):
    qty: Money = Field(gt=Decimal("0"))
    unit: str
    price_per_purchase_unit: Money = Field(ge=Decimal("0"))
    purchase_unit: str


class PreviewRequest(BaseModel):
    line_items: Annotated[list[PreviewLineItem], Field(min_length=1)]
    prep_minutes: int = Field(ge=0, le=1440)
    audience: Audience | None = None


class PreviewResponse(BaseModel):
    materials: Money
    waste: Money
    materials_con_merma: Money
    labor: Money
    gas: Money
    base: Money
    margin_pct: Money
    final: Money
    rounded: Money
    audience: Audience

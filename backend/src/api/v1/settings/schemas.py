from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.v1.money import Money, Pct


class SettingsUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    hourly_rate: Money = Field(ge=1, le=10_000_000)
    margin_pct: Pct = Field(ge=0, le=100)
    round_step: Money = Field(ge=1, le=100_000)
    include_labor: bool = True
    include_gas: bool = True
    gas_pct: Pct = Field(default=Decimal("3"), ge=0, le=100)
    include_waste: bool = True
    waste_pct: Pct = Field(default=Decimal("3"), ge=0, le=100)
    urgent_surcharge_pct: Pct = Field(
        default=Decimal("20"), ge=0, le=100
    )
    consumer_markup_pct: Pct = Field(default=Decimal("40"), ge=0, le=100)
    default_prep_minutes: int = Field(default=30, ge=0, le=1440)
    default_servings: int = Field(default=6, ge=1, le=999)
    default_difficulty: Literal["simple", "intermedio", "complejo"] = "simple"
    business_name: str = Field(default="", max_length=120)
    footer_text: str = Field(default="", max_length=280)

    @model_validator(mode="after")
    def _check_toggle_dependencies(self) -> "SettingsUpdate":
        if not self.include_gas and self.gas_pct != Decimal("0"):
            raise ValueError("gas_pct debe ser 0 si include_gas esta desactivado")
        if not self.include_waste and self.waste_pct != Decimal("0"):
            raise ValueError("waste_pct debe ser 0 si include_waste esta desactivado")
        return self


class SettingsResponse(BaseModel):
    hourly_rate: Money
    margin_pct: Pct
    round_step: Money
    include_labor: bool
    include_gas: bool
    gas_pct: Pct
    include_waste: bool
    waste_pct: Pct
    urgent_surcharge_pct: Pct
    default_prep_minutes: int
    default_servings: int
    default_difficulty: str
    business_name: str
    footer_text: str


class AdminSettingsResponse(SettingsResponse):

    consumer_markup_pct: Pct

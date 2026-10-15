from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money


class SettingsUpdate(BaseModel):
    """Body de PUT /settings. Los rangos son los de la spec (api_endpoints.md §5.2).

    extra="forbid": un campo desconocido es 422, no un silencio que se pierde
    entre el frontend y la base.
    """

    model_config = ConfigDict(extra="forbid")

    hourly_rate: Money = Field(ge=Decimal("0.01"), le=Decimal("100000"))
    margin_pct: Money = Field(ge=Decimal("10"), le=Decimal("200"))
    round_step: Money = Field(ge=Decimal("0.01"), le=Decimal("1000"))
    include_labor: bool = True
    include_gas: bool = False
    gas_pct: Money = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("100"))
    include_waste: bool = False
    waste_pct: Money = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("100"))
    default_prep_minutes: int = Field(default=30, ge=0, le=1440)
    default_servings: int = Field(default=6, ge=1, le=999)
    default_difficulty: Literal["simple", "intermedio", "complejo"] = "simple"


class SettingsResponse(BaseModel):
    hourly_rate: Money
    margin_pct: Money
    round_step: Money
    include_labor: bool
    include_gas: bool
    gas_pct: Money
    include_waste: bool
    waste_pct: Money
    default_prep_minutes: int
    default_servings: int
    default_difficulty: str

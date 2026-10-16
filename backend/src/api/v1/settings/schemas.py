from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.v1.money import Money


class SettingsUpdate(BaseModel):
    """Body de PUT /tenant/settings. Los rangos son los de la spec p05 (RF-P5-01):
    margen 0-100, hora 0.01-100000, paso 0.01-1000, gas/merma/urgencia 0-100.

    extra="forbid": un campo desconocido es 422, no un silencio que se pierde
    entre el frontend y la base.
    Los defaults del schema son los del sistema (RF-P5-04).
    """

    model_config = ConfigDict(extra="forbid")

    hourly_rate: Money = Field(ge=Decimal("0.01"), le=Decimal("100000"))
    margin_pct: Money = Field(ge=Decimal("0"), le=Decimal("100"))
    round_step: Money = Field(ge=Decimal("0.01"), le=Decimal("1000"))
    include_labor: bool = True
    include_gas: bool = True
    gas_pct: Money = Field(default=Decimal("3"), ge=Decimal("0"), le=Decimal("100"))
    include_waste: bool = True
    waste_pct: Money = Field(default=Decimal("3"), ge=Decimal("0"), le=Decimal("100"))
    urgent_surcharge_pct: Money = Field(
        default=Decimal("20"), ge=Decimal("0"), le=Decimal("100")
    )
    default_prep_minutes: int = Field(default=30, ge=0, le=1440)
    default_servings: int = Field(default=6, ge=1, le=999)
    default_difficulty: Literal["simple", "intermedio", "complejo"] = "simple"

    @model_validator(mode="after")
    def _check_toggle_dependencies(self) -> "SettingsUpdate":
        """RF-P5-06: cada % exige su toggle encendido. Se valida en el schema
        para que el rechazo sea 422 (el 400 del dominio queda como segunda
        linea para quien construya BusinessSettings programaticamente)."""
        if not self.include_gas and self.gas_pct != Decimal("0"):
            raise ValueError("gas_pct debe ser 0 si include_gas esta desactivado")
        if not self.include_waste and self.waste_pct != Decimal("0"):
            raise ValueError("waste_pct debe ser 0 si include_waste esta desactivado")
        return self


class SettingsResponse(BaseModel):
    hourly_rate: Money
    margin_pct: Money
    round_step: Money
    include_labor: bool
    include_gas: bool
    gas_pct: Money
    include_waste: bool
    waste_pct: Money
    urgent_surcharge_pct: Money
    default_prep_minutes: int
    default_servings: int
    default_difficulty: str

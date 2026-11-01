from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.v1.money import Money, Pct


class SettingsUpdate(BaseModel):
    """Body de PUT /tenant/settings. Los rangos son los de la spec p05 (RF-P5-01):
    margen 0-100, hora 0.01-100000, paso 0.01-1000, gas/merma/urgencia 0-100.

    Money viaja en centavos (long): hora 1-10_000_000, paso 1-100_000.
    Los % (Pct) siguen siendo porcentaje plano 0-100, NO centavos.

    extra="forbid": un campo desconocido es 422, no un silencio que se pierde
    entre el frontend y la base.
    Los defaults del schema son los del sistema (RF-P5-04).
    """

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
    # Porcentaje plano 0-100 (Pct), NO centavos: 40 = 40% (S2/T8).
    consumer_markup_pct: Pct = Field(default=Decimal("40"), ge=0, le=100)
    default_prep_minutes: int = Field(default=30, ge=0, le=1440)
    default_servings: int = Field(default=6, ge=1, le=999)
    default_difficulty: Literal["simple", "intermedio", "complejo"] = "simple"
    # Fase 8 (P9): branding del PDF (solo texto; sin upload de logo en v1).
    business_name: str = Field(default="", max_length=120)
    footer_text: str = Field(default="", max_length=280)

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
    # Fase 8 (P9): branding del PDF.
    business_name: str
    footer_text: str


class AdminSettingsResponse(SettingsResponse):
    """Solo admin: agrega el markup de consumidor final, que un revendedor
    o cliente no debe poder leer."""

    consumer_markup_pct: Pct

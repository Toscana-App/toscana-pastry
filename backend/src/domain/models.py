import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from enum import Enum

from domain.pricing import PricingSettings


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"


DIFFICULTIES = ("simple", "intermedio", "complejo")


@dataclass(frozen=True)
class User:
    """Entidad de dominio. La identidad la genera el propio dominio: quien crea
    un User no necesita conocer ni construir el id."""

    email: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: UserRole = UserRole.CUSTOMER
    google_id: Optional[str] = None


@dataclass
class BusinessSettings:
    """Parametros de precio de la casa. Un solo registro: la app es monotenante.

    Los rangos validados son los de la spec (api_endpoints.md §5.2):
    valor hora 0.01-100000, margen 10-200, paso 0.01-1000, gas/merma 0-100.
    """

    hourly_rate: Decimal
    margin_pct: Decimal
    round_step: Decimal
    include_labor: bool = True
    include_gas: bool = False
    gas_pct: Decimal = Decimal("0")
    include_waste: bool = False
    waste_pct: Decimal = Decimal("0")
    default_prep_minutes: int = 30
    default_servings: int = 6
    default_difficulty: str = "simple"

    def __post_init__(self):
        if not Decimal("0.01") <= self.hourly_rate <= Decimal("100000"):
            raise ValueError(
                f"hourly_rate fuera de rango 0.01-100000: {self.hourly_rate}"
            )
        if not Decimal("10") <= self.margin_pct <= Decimal("200"):
            raise ValueError(f"margin_pct fuera de rango 10-200: {self.margin_pct}")
        if not Decimal("0.01") <= self.round_step <= Decimal("1000"):
            raise ValueError(f"round_step fuera de rango 0.01-1000: {self.round_step}")
        if not Decimal("0") <= self.gas_pct <= Decimal("100"):
            raise ValueError(f"gas_pct fuera de rango 0-100: {self.gas_pct}")
        if not Decimal("0") <= self.waste_pct <= Decimal("100"):
            raise ValueError(f"waste_pct fuera de rango 0-100: {self.waste_pct}")
        if not 0 <= self.default_prep_minutes <= 1440:
            raise ValueError(
                f"default_prep_minutes fuera de rango 0-1440: {self.default_prep_minutes}"
            )
        if not 1 <= self.default_servings <= 999:
            raise ValueError(f"default_servings fuera de rango 1-999: {self.default_servings}")
        if self.default_difficulty not in DIFFICULTIES:
            raise ValueError(f"default_difficulty invalido: {self.default_difficulty!r}")

    def to_pricing(self) -> PricingSettings:
        """La porcion de estos parametros que entra en la formula."""
        return PricingSettings(
            hourly_rate=self.hourly_rate,
            margin_pct=self.margin_pct,
            round_step=self.round_step,
            include_labor=self.include_labor,
            include_gas=self.include_gas,
            gas_pct=self.gas_pct,
            include_waste=self.include_waste,
            waste_pct=self.waste_pct,
        )


DEFAULT_BUSINESS_SETTINGS = BusinessSettings(
    hourly_rate=Decimal("150"),
    margin_pct=Decimal("100"),
    round_step=Decimal("5"),
)

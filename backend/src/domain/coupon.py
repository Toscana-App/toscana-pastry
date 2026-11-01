"""Dominio de cupones (RF-P11-14, C3).

Entidad frozen con __post_init__ para validacion de invariantes:
- code no-blank y <= MAX_COUPON_CODE (unicidad case-insensitive la
  garantiza el repositorio, estilo accent_fold de calc).
- type=percent → value 0–100; type=fixed → value Money ≥ 0.
- Si valid_from y valid_until estan presentes, valid_until > valid_from.
- max_uses positiva si presente; uses inicia 0 (se incrementa en C4
  al confirmar el pedido, nunca en C3).
- status ∈ {active, paused}, default active.
"""
import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

ALLOWED_COUPON_TYPES = ("percent", "fixed")
ALLOWED_COUPON_STATUSES = ("active", "paused")

# Longitud maxima del code (cortos y legibles: "VERANO10", "CAFÉ10").
MAX_COUPON_CODE = 32

class DuplicateCouponCodeError(Exception):
    """El code (case/accent-insensitive) ya existe: viola code_key UNIQUE."""


PERCENT_MAX = Decimal("100")
MONEY_MIN = Decimal("0")


def _aware_utc(
    dt: datetime.datetime | None,
) -> datetime.datetime | None:
    """Normaliza a aware UTC: naive se asume UTC (SQLite devuelve naive
    en el round-trip), aware se convierte a UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.UTC)
    return dt.astimezone(datetime.UTC)


@dataclass(frozen=True)
class Coupon:
    """Cupon de descuento (RF-P11-14)."""

    code: str
    type: Literal["percent", "fixed"]
    value: Decimal
    valid_from: datetime.datetime | None = None
    valid_until: datetime.datetime | None = None
    max_uses: int | None = None
    status: str = "active"
    uses: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self):
        object.__setattr__(self, "valid_from", _aware_utc(self.valid_from))
        object.__setattr__(
            self, "valid_until", _aware_utc(self.valid_until)
        )
        code = self.code.strip()
        if not code:
            raise ValueError("code requerido y no puede ser solo espacios")
        if len(code) > MAX_COUPON_CODE:
            raise ValueError(
                f"code maximo {MAX_COUPON_CODE}: {len(code)}"
            )
        if self.type not in ALLOWED_COUPON_TYPES:
            raise ValueError(
                f"type invalido: {self.type!r} "
                f"(permitido: {ALLOWED_COUPON_TYPES})"
            )
        if self.type == "percent":
            if not (MONEY_MIN <= self.value <= PERCENT_MAX):
                raise ValueError(
                    f"type=percent exige value 0-100: {self.value}"
                )
        else:  # fixed
            if self.value < MONEY_MIN:
                raise ValueError(
                    f"type=fixed exige value >= 0: {self.value}"
                )
        if self.status not in ALLOWED_COUPON_STATUSES:
            raise ValueError(
                f"status invalido: {self.status!r} "
                f"(permitido: {ALLOWED_COUPON_STATUSES})"
            )
        if self.max_uses is not None and self.max_uses < 1:
            raise ValueError(
                f"max_uses debe ser positiva: {self.max_uses}"
            )
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until <= self.valid_from
        ):
            raise ValueError(
                "valid_until debe ser estrictamente mayor que valid_from"
            )
        if self.uses < 0:
            raise ValueError(f"uses no puede ser negativo: {self.uses}")

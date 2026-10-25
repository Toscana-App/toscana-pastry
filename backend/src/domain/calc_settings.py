"""Dominio de la configuracion de la calculadora de costos (P5-CC).

Entidades frozen con __post_init__ para validacion de rangos y listas
permitidas. Money siempre Decimal, nunca float (RNF-P5CC-01).
"""
import re
import uuid
import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Optional

ALLOWED_ROUNDING_MODES = ("none", "integer", "multiple_10", "commercial_99")
ALLOWED_DEFAULT_COST_TYPES = ("labor", "extra_cost")
ALLOWED_DEFAULT_COST_STATUSES = ("active", "inactive")

# Default values (RF-P5CC-01)
DEFAULT_BUSINESS_NAME = "Mi Negocio"
DEFAULT_MAIN_CURRENCY_NAME = "Peso"
DEFAULT_MAIN_CURRENCY_SYMBOL = "$"
DEFAULT_MARGIN_PERCENT = Decimal("30")
DEFAULT_DISCOUNT_PERCENT = Decimal("0")
DEFAULT_TAX_PERCENT = Decimal("19")
DEFAULT_ROUNDING_MODE = "none"

# String length limits (RF-P5CC-01..05)
MAX_BUSINESS_NAME = 120
MAX_CURRENCY_NAME = 40
MAX_CURRENCY_SYMBOL = 8
MAX_MATERIAL_CATEGORY_NAME = 80
MAX_MATERIAL_CATEGORY_DESCRIPTION = 200
MAX_PRODUCT_CATEGORY_NAME = 80
MAX_PRODUCT_CATEGORY_DESCRIPTION = 200
MAX_SUPPLIER_NAME = 120
MAX_SUPPLIER_CONTACT_NAME = 120
MAX_SUPPLIER_PHONE = 30
MAX_SUPPLIER_EMAIL = 120
MAX_SUPPLIER_NOTES = 500
MAX_DEFAULT_COST_NAME = 120

# Email regex (basic)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value))


@dataclass(frozen=True)
class CalcSettings:
    """Configuracion general de la calculadora (singleton).

    RF-P5CC-01: campos, rangos y valores por defecto.
    """

    business_name: str = DEFAULT_BUSINESS_NAME
    main_currency_name: str = DEFAULT_MAIN_CURRENCY_NAME
    main_currency_symbol: str = DEFAULT_MAIN_CURRENCY_SYMBOL
    default_margin_percent: Decimal = DEFAULT_MARGIN_PERCENT
    default_discount_percent: Decimal = DEFAULT_DISCOUNT_PERCENT
    default_tax_percent: Decimal = DEFAULT_TAX_PERCENT
    rounding_mode: str = DEFAULT_ROUNDING_MODE

    def __post_init__(self):
        if not (1 <= len(self.business_name) <= MAX_BUSINESS_NAME):
            raise ValueError(
                f"business_name longitud 1-{MAX_BUSINESS_NAME}: "
                f"{len(self.business_name)}"
            )
        if not (1 <= len(self.main_currency_name) <= MAX_CURRENCY_NAME):
            raise ValueError(
                f"main_currency_name longitud 1-{MAX_CURRENCY_NAME}: "
                f"{len(self.main_currency_name)}"
            )
        if not (1 <= len(self.main_currency_symbol) <= MAX_CURRENCY_SYMBOL):
            raise ValueError(
                f"main_currency_symbol longitud 1-{MAX_CURRENCY_SYMBOL}: "
                f"{len(self.main_currency_symbol)}"
            )
        if not (Decimal("0") <= self.default_margin_percent <= Decimal("100")):
            raise ValueError(
                f"default_margin_percent 0-100: {self.default_margin_percent}"
            )
        if not (Decimal("0") <= self.default_discount_percent <= Decimal("100")):
            raise ValueError(
                f"default_discount_percent 0-100: {self.default_discount_percent}"
            )
        if not (Decimal("0") <= self.default_tax_percent <= Decimal("100")):
            raise ValueError(
                f"default_tax_percent 0-100: {self.default_tax_percent}"
            )
        if self.rounding_mode not in ALLOWED_ROUNDING_MODES:
            raise ValueError(
                f"rounding_mode invalido: {self.rounding_mode!r} "
                f"(permitido: {ALLOWED_ROUNDING_MODES})"
            )


# Constante de defaults del sistema (RF-P5CC-01)
DEFAULT_CALC_SETTINGS = CalcSettings()


@dataclass(frozen=True)
class CalcMaterialCategory:
    """Categoria de materiales (RF-P5CC-03)."""

    name: str
    description: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_MATERIAL_CATEGORY_NAME):
            raise ValueError(
                f"name longitud 1-{MAX_MATERIAL_CATEGORY_NAME}: {len(name)}"
            )
        if self.description is not None and len(self.description) > MAX_MATERIAL_CATEGORY_DESCRIPTION:
            raise ValueError(
                f"description max {MAX_MATERIAL_CATEGORY_DESCRIPTION}: "
                f"{len(self.description)}"
            )


@dataclass(frozen=True)
class CalcProductCategory:
    """Categoria de productos (RF-P5CC-04). Mismas reglas que RF-P5CC-03."""

    name: str
    description: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_PRODUCT_CATEGORY_NAME):
            raise ValueError(
                f"name longitud 1-{MAX_PRODUCT_CATEGORY_NAME}: {len(name)}"
            )
        if self.description is not None and len(self.description) > MAX_PRODUCT_CATEGORY_DESCRIPTION:
            raise ValueError(
                f"description max {MAX_PRODUCT_CATEGORY_DESCRIPTION}: "
                f"{len(self.description)}"
            )


@dataclass(frozen=True)
class CalcSupplier:
    """Proveedor (RF-P5CC-05)."""

    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_SUPPLIER_NAME):
            raise ValueError(
                f"name longitud 1-{MAX_SUPPLIER_NAME}: {len(name)}"
            )
        if self.contact_name is not None and len(self.contact_name) > MAX_SUPPLIER_CONTACT_NAME:
            raise ValueError(
                f"contact_name max {MAX_SUPPLIER_CONTACT_NAME}: "
                f"{len(self.contact_name)}"
            )
        if self.phone is not None and len(self.phone) > MAX_SUPPLIER_PHONE:
            raise ValueError(
                f"phone max {MAX_SUPPLIER_PHONE}: {len(self.phone)}"
            )
        if self.email is not None:
            if len(self.email) > MAX_SUPPLIER_EMAIL:
                raise ValueError(
                    f"email max {MAX_SUPPLIER_EMAIL}: {len(self.email)}"
                )
            if not _is_valid_email(self.email):
                raise ValueError(f"email invalido: {self.email!r}")
        if self.notes is not None and len(self.notes) > MAX_SUPPLIER_NOTES:
            raise ValueError(
                f"notes max {MAX_SUPPLIER_NOTES}: {len(self.notes)}"
            )


@dataclass(frozen=True)
class CalcDefaultCost:
    """Costo por defecto (RF-P5CC-06)."""

    name: str
    type: Literal["labor", "extra_cost"]
    default_unit_cost_or_rate: Decimal
    default_quantity_or_minutes: Decimal
    status: str = "active"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_DEFAULT_COST_NAME):
            raise ValueError(
                f"name longitud 1-{MAX_DEFAULT_COST_NAME}: {len(name)}"
            )
        if self.type not in ALLOWED_DEFAULT_COST_TYPES:
            raise ValueError(
                f"type invalido: {self.type!r} "
                f"(permitido: {ALLOWED_DEFAULT_COST_TYPES})"
            )
        if self.default_unit_cost_or_rate < Decimal("0"):
            raise ValueError(
                f"default_unit_cost_or_rate >= 0: {self.default_unit_cost_or_rate}"
            )
        if self.default_quantity_or_minutes < Decimal("0"):
            raise ValueError(
                f"default_quantity_or_minutes >= 0: {self.default_quantity_or_minutes}"
            )
        if self.status not in ALLOWED_DEFAULT_COST_STATUSES:
            raise ValueError(
                f"status invalido: {self.status!r} "
                f"(permitido: {ALLOWED_DEFAULT_COST_STATUSES})"
            )

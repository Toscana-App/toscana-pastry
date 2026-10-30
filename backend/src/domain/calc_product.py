"""Dominio de productos de la calculadora de costos (P4-CC).

Motor de precio con paridad exacta contra `pricing.js` legacy
(`calcProductPricing` / `applyRounding`): todo Decimal + ROUND_HALF_UP,
el float nunca toca un monto (RNF-P4-03 / RNF-P5CC-01). Entidades frozen
con `__post_init__` (estilo `domain/calc_material.py`).

`line_total_cost`, los snapshots de material y los 6 montos de `costs`
son SIEMPRE derivados del servidor (RF-P4CC-02/05, security #8):
ningun valor de entrada del cliente los fija.
"""

import dataclasses
import datetime
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

# String length limits (RF-P4CC-01)
MAX_PRODUCT_NAME = 120
MAX_PRODUCT_SKU = 40
MAX_PRODUCT_DESCRIPTION = 500
MAX_PRODUCT_NOTES = 500
MAX_LINE_NAME = 120

# Status allow-list (RF-P4CC-01)
PRODUCT_STATUS_DRAFT = "draft"
PRODUCT_STATUS_ACTIVE = "active"
PRODUCT_STATUS_ARCHIVED = "archived"
ALLOWED_PRODUCT_STATUSES = (
    PRODUCT_STATUS_DRAFT,
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_ARCHIVED,
)

_ZERO = Decimal("0")
_CENTS = Decimal("0.01")
_HUNDRED = Decimal("100")


def _cents(value: Decimal) -> Decimal:
    """Cuantiza a centavos con ROUND_HALF_UP (RNF-P4-03)."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _check_non_negative(name: str, value: Decimal | None) -> Decimal:
    """Faltar valor -> 0 (paridad `|| 0` del JS); negativo -> ValueError."""
    if value is None:
        return _ZERO
    if value < _ZERO:
        raise ValueError(f"{name} >= 0: {value}")
    return value


def calc_material_line_cost(quantity_used, unit_cost) -> Decimal:
    """line = quantity_used x unit_cost (RF-P4CC-02).

    Faltando un valor cuenta como 0 (paridad del `|| 0` del JS, D4);
    negativos -> ValueError (422 en la API). Resultado en centavos.
    """
    quantity = _check_non_negative("quantity_used", quantity_used)
    cost = _check_non_negative("unit_cost", unit_cost)
    return _cents(quantity * cost)


def calc_labor_line_cost(hourly_rate, minutes_required) -> Decimal:
    """line = hourly_rate x (minutes_required / 60) (RF-P4CC-02)."""
    rate = _check_non_negative("hourly_rate", hourly_rate)
    minutes = _check_non_negative("minutes_required", minutes_required)
    return _cents(rate * (minutes / Decimal("60")))


def calc_extra_line_cost(unit_cost, quantity) -> Decimal:
    """line = unit_cost x quantity (RF-P4CC-02)."""
    cost = _check_non_negative("unit_cost", unit_cost)
    qty = _check_non_negative("quantity", quantity)
    return _cents(cost * qty)


def _check_percent(name: str, value: Decimal) -> Decimal:
    """Percents de margin/descuento/impuesto: 0-100 (RF-P4CC-03)."""
    if not (_ZERO <= value <= _HUNDRED):
        raise ValueError(f"{name} 0-100: {value}")
    return value


@dataclass(frozen=True)
class CalcProductCosts:
    """Desglose de 6 montos (RF-P4CC-05), SIEMPRE en centavos.

    Nombres y orden identicos a `calcProductPricing` de pricing.js.
    El redondeo comercial (RF-P4CC-04) se aplica SOLO a
    `final_sale_price`, nunca a los otros cinco (ver `compute_costs`).
    """

    product_total_cost: Decimal
    profit_amount: Decimal
    discount_amount: Decimal
    adjusted_profit_amount: Decimal
    tax_amount: Decimal
    final_sale_price: Decimal


def calc_product_pricing(
    materials_cost_total: Decimal,
    labor_cost_total: Decimal,
    extra_cost_total: Decimal,
    margin_percent: Decimal,
    discount_percent: Decimal,
    tax_percent: Decimal,
) -> CalcProductCosts:
    """Motor de precio (RF-P4CC-03), paridad line a line con pricing.js.

    Orden de calculo identico al JS: cost -> margen (guarda para
    margin >= 100) -> ganancia -> descuento -> ganancia ajustada ->
    impuesto -> precio final. Todos los montos cuantizados a centavos
    con ROUND_HALF_UP; percents fuera de [0, 100] -> ValueError.
    """
    margin = _check_percent("margin_percent", margin_percent)
    discount = _check_percent("discount_percent", discount_percent)
    tax = _check_percent("tax_percent", tax_percent)

    cost_total = _cents(materials_cost_total + labor_cost_total + extra_cost_total)
    # Guarda RF-P4CC-03: margin >= 100 evitara la division por cero.
    if margin >= _HUNDRED:
        price_before_discount = cost_total
    else:
        price_before_discount = _cents(
            cost_total / (_HUNDRED - margin) * _HUNDRED
        )
    profit_amount = _cents(price_before_discount - cost_total)
    discount_amount = _cents(
        -(cost_total + profit_amount) * discount / _HUNDRED
    )
    adjusted_profit_amount = _cents(profit_amount + discount_amount)
    tax_amount = _cents((cost_total + adjusted_profit_amount) * tax / _HUNDRED)
    final_sale_price = _cents(cost_total + adjusted_profit_amount + tax_amount)
    return CalcProductCosts(
        product_total_cost=cost_total,
        profit_amount=profit_amount,
        discount_amount=discount_amount,
        adjusted_profit_amount=adjusted_profit_amount,
        tax_amount=tax_amount,
        final_sale_price=final_sale_price,
    )


def apply_rounding(value: Decimal, mode: str) -> Decimal:
    """Redondeo comercial del precio final (RF-P4CC-04).

    Se aplica SOLO a `final_sale_price`. Modos permitidos:
    none / integer / multiple_10 / commercial_99; modo desconocido
    -> ValueError (422 en la API).
    """
    if mode == "none":
        return value
    if mode == "integer":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if mode == "multiple_10":
        return (value / Decimal("10")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ) * Decimal("10")
    if mode == "commercial_99":
        return (
            (value / Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
            * Decimal("100")
            - Decimal("1")
        )
    raise ValueError(
        f"rounding_mode desconocido: {mode!r} "
        "(permitido: none, integer, multiple_10, commercial_99)"
    )


def compute_costs(
    material_lines: list,
    labor_lines: list,
    extra_lines: list,
    margin_percent: Decimal,
    discount_percent: Decimal,
    tax_percent: Decimal,
    rounding_mode: str,
) -> CalcProductCosts:
    """Costs de un producto desde sus lineas + percents + modo de
    redondeo de settings (RF-P4CC-05/04). Siempre del servidor.

    `rounding_mode` se aplica solo al `final_sale_price`; los otros
    cinco montos quedan en centavos sin redondeo comercial.
    """
    costs = calc_product_pricing(
        sum((line.line_total_cost for line in material_lines), _ZERO),
        sum((line.line_total_cost for line in labor_lines), _ZERO),
        sum((line.line_total_cost for line in extra_lines), _ZERO),
        margin_percent,
        discount_percent,
        tax_percent,
    )
    return dataclasses.replace(
        costs,
        final_sale_price=apply_rounding(costs.final_sale_price, rounding_mode),
    )


def _check_line_name(name: str | None) -> str:
    """Nombre de linea (actividad/concepto): 1-MAX_LINE_NAME, no vacio."""
    if name is None:
        raise ValueError("name de linea requerido")
    value = name.strip()
    if not value:
        raise ValueError("name de linea no puede ser solo espacios")
    if len(value) > MAX_LINE_NAME:
        raise ValueError(f"name de linea max {MAX_LINE_NAME}: {len(value)}")
    return value


@dataclass(frozen=True)
class CalcProductMaterialLine:
    """Linea de material con snapshots resueltos por el servidor
    (RF-P4CC-02, security #8): `material_name`, `unit_of_measure_snapshot`
    y `unit_cost_snapshot` provienen de `calc_materials` al guardar;
    material `incomplete` (unit_cost None) -> snapshot en 0.00 (D4).
    """

    material_id: str
    material_name: str
    quantity_used: Decimal
    unit_of_measure_snapshot: str | None
    unit_cost_snapshot: Decimal
    line_total_cost: Decimal
    sort_order: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if self.quantity_used < _ZERO:
            raise ValueError(f"quantity_used >= 0: {self.quantity_used}")
        if self.unit_cost_snapshot < _ZERO:
            raise ValueError(f"unit_cost_snapshot >= 0: {self.unit_cost_snapshot}")


@dataclass(frozen=True)
class CalcProductLaborLine:
    """Linea de mano de obra (RF-P4CC-02)."""

    activity_name: str
    hourly_rate: Decimal
    minutes_required: Decimal
    line_total_cost: Decimal
    sort_order: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "activity_name", _check_line_name(self.activity_name))
        if self.hourly_rate < _ZERO:
            raise ValueError(f"hourly_rate >= 0: {self.hourly_rate}")
        if self.minutes_required < _ZERO:
            raise ValueError(f"minutes_required >= 0: {self.minutes_required}")


@dataclass(frozen=True)
class CalcProductExtraCostLine:
    """Linea de costo extra (RF-P4CC-02)."""

    concept_name: str
    unit_cost: Decimal
    quantity: Decimal
    line_total_cost: Decimal
    sort_order: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "concept_name", _check_line_name(self.concept_name))
        if self.unit_cost < _ZERO:
            raise ValueError(f"unit_cost >= 0: {self.unit_cost}")
        if self.quantity < _ZERO:
            raise ValueError(f"quantity >= 0: {self.quantity}")


@dataclass(frozen=True)
class CalcProduct:
    """Producto de la calculadora de costos (RF-P4CC-01).

    Percents 0-100 (defaults del singleton `CalcSettings` cuando el
    payload no los envia, RF-P5CC-01); `status` con allow-list
    draft/active/archived; soft delete via `deleted_at` (S4).
    """

    name: str
    margin_percent: Decimal
    sku: str | None = None
    category_id: str | None = None
    description: str | None = None
    notes: str | None = None
    discount_percent: Decimal = _ZERO
    tax_percent: Decimal = _ZERO
    status: str = PRODUCT_STATUS_DRAFT
    last_recalculated_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self):
        name = self.name.strip()
        if not name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not (1 <= len(name) <= MAX_PRODUCT_NAME):
            raise ValueError(f"name longitud 1-{MAX_PRODUCT_NAME}: {len(name)}")
        object.__setattr__(self, "name", name)

        if self.sku is not None:
            sku = self.sku.strip()
            if not sku:
                object.__setattr__(self, "sku", None)
            else:
                if len(sku) > MAX_PRODUCT_SKU:
                    raise ValueError(
                        f"sku max {MAX_PRODUCT_SKU}: {len(sku)}"
                    )
                object.__setattr__(self, "sku", sku)
        if self.description is not None and len(self.description) > MAX_PRODUCT_DESCRIPTION:
            raise ValueError(
                f"description max {MAX_PRODUCT_DESCRIPTION}: {len(self.description)}"
            )
        if self.notes is not None and len(self.notes) > MAX_PRODUCT_NOTES:
            raise ValueError(f"notes max {MAX_PRODUCT_NOTES}: {len(self.notes)}")

        object.__setattr__(
            self,
            "margin_percent",
            _check_percent("margin_percent", self.margin_percent),
        )
        object.__setattr__(
            self,
            "discount_percent",
            _check_percent("discount_percent", self.discount_percent),
        )
        object.__setattr__(
            self,
            "tax_percent",
            _check_percent("tax_percent", self.tax_percent),
        )
        if self.status not in ALLOWED_PRODUCT_STATUSES:
            raise ValueError(
                f"status invalido: {self.status!r} "
                f"(permitido: {ALLOWED_PRODUCT_STATUSES})"
            )


@dataclass(frozen=True)
class CalcProductVersion:
    """Fila append-only de versiones de precio (RF-P4CC-07).

    Solo se INSERTA (en `POST /{id}/recalculate` cuando el final
    redondeado cambio), nunca se UPDATE/DELETE. `version_number`
    = max anterior + 1 (primera version = 1).
    """

    product_id: str
    version_number: int
    product_total_cost: Decimal
    profit_amount: Decimal
    discount_amount: Decimal
    adjusted_profit_amount: Decimal
    tax_amount: Decimal
    final_sale_price: Decimal
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    changed_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self):
        if self.version_number < 1:
            raise ValueError(f"version_number >= 1: {self.version_number}")

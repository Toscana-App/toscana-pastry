
import dataclasses
import datetime
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Mapping

from domain.calc_material import CalcMaterial

MAX_PRODUCT_NAME = 120
MAX_PRODUCT_SKU = 40
MAX_PRODUCT_DESCRIPTION = 500
MAX_PRODUCT_NOTES = 500
MAX_LINE_NAME = 120

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
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _check_non_negative(name: str, value: Decimal | None) -> Decimal:
    if value is None:
        return _ZERO
    if value < _ZERO:
        raise ValueError(f"{name} >= 0: {value}")
    return value


def calc_material_line_cost(quantity_used, unit_cost) -> Decimal:
    quantity = _check_non_negative("quantity_used", quantity_used)
    cost = _check_non_negative("unit_cost", unit_cost)
    return _cents(quantity * cost)


def calc_labor_line_cost(hourly_rate, minutes_required) -> Decimal:
    rate = _check_non_negative("hourly_rate", hourly_rate)
    minutes = _check_non_negative("minutes_required", minutes_required)
    return _cents(rate * (minutes / Decimal("60")))


def calc_extra_line_cost(unit_cost, quantity) -> Decimal:
    cost = _check_non_negative("unit_cost", unit_cost)
    qty = _check_non_negative("quantity", quantity)
    return _cents(cost * qty)


def _check_percent(name: str, value: Decimal) -> Decimal:
    if not (_ZERO <= value <= _HUNDRED):
        raise ValueError(f"{name} 0-100: {value}")
    return value


@dataclass(frozen=True)
class CalcProductCosts:

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
    margin = _check_percent("margin_percent", margin_percent)
    discount = _check_percent("discount_percent", discount_percent)
    tax = _check_percent("tax_percent", tax_percent)

    cost_total = _cents(materials_cost_total + labor_cost_total + extra_cost_total)
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


def resolve_material_line(
    material: CalcMaterial,
    quantity_used: Decimal,
    sort_order: int,
    line_id: str | None = None,
) -> CalcProductMaterialLine:
    unit_cost = (
        Decimal(material.unit_cost)
        if material.unit_cost is not None
        else Decimal("0.00")
    )
    extra = {} if line_id is None else {"id": line_id}
    return CalcProductMaterialLine(
        material_id=material.id,
        material_name=material.name,
        quantity_used=quantity_used,
        unit_of_measure_snapshot=material.unit_of_measure,
        unit_cost_snapshot=unit_cost,
        line_total_cost=calc_material_line_cost(quantity_used, unit_cost),
        sort_order=sort_order,
        **extra,
    )


@dataclass(frozen=True)
class RecalculationResult:

    material_lines: list[CalcProductMaterialLine]
    labor_lines: list[CalcProductLaborLine]
    extra_lines: list[CalcProductExtraCostLine]
    old_costs: CalcProductCosts
    new_costs: CalcProductCosts

    @property
    def creates_version(self) -> bool:
        return self.new_costs.final_sale_price != self.old_costs.final_sale_price


def recalculate_product(
    product: CalcProduct,
    material_lines: list[CalcProductMaterialLine],
    labor_lines: list[CalcProductLaborLine],
    extra_lines: list[CalcProductExtraCostLine],
    materials_by_id: Mapping[str, CalcMaterial],
    rounding_mode: str,
) -> RecalculationResult:

    def _costs(materials, labor, extras) -> CalcProductCosts:
        return compute_costs(
            materials,
            labor,
            extras,
            product.margin_percent,
            product.discount_percent,
            product.tax_percent,
            rounding_mode,
        )

    old_costs = _costs(material_lines, labor_lines, extra_lines)
    new_materials = [
        resolve_material_line(
            materials_by_id[line.material_id],
            line.quantity_used,
            line.sort_order,
            line_id=line.id,
        )
        if line.material_id in materials_by_id
        else line
        for line in material_lines
    ]
    new_labor = [
        dataclasses.replace(
            line,
            line_total_cost=calc_labor_line_cost(
                line.hourly_rate, line.minutes_required
            ),
        )
        for line in labor_lines
    ]
    new_extras = [
        dataclasses.replace(
            line,
            line_total_cost=calc_extra_line_cost(line.unit_cost, line.quantity),
        )
        for line in extra_lines
    ]
    return RecalculationResult(
        material_lines=new_materials,
        labor_lines=new_labor,
        extra_lines=new_extras,
        old_costs=old_costs,
        new_costs=_costs(new_materials, new_labor, new_extras),
    )

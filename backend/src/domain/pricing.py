"""Motor de precios de Toscana Pastry.

Módulo puro: Decimal adentro, Decimal afuera. Sin frameworks, sin I/O.
La formula sigue master_plan.md §1.3; el modo de redondeo es
ROUND_HALF_UP al paso configurado (RNF-P4-03).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

# Factor de conversion a la unidad base de cada familia:
# peso -> g, volumen -> ml, unidad -> unidad.
_BASE_FACTORS = {
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "ml": Decimal("1"),
    "l": Decimal("1000"),
    "unidad": Decimal("1"),
}

_UNIT_FAMILY = {
    "g": "peso",
    "kg": "peso",
    "ml": "volumen",
    "l": "volumen",
    "unidad": "unidad",
}


def _fold_unit(unit: str) -> str:
    # El contrato de ingredientes usa "L" mayuscula (STOCK_UNITS) y el
    # preview usa "l": ambas equivalen sin migrar datos existentes.
    return unit.casefold() if isinstance(unit, str) else unit


_CENT = Decimal("0.01")


class UnitConversionError(ValueError):
    """Unidades desconocidas o incompatibles entre receta y compra."""


def to_base_units(qty: Decimal, unit: str) -> Decimal:
    """Cantidad expresada en la unidad base de su familia."""
    factor = _BASE_FACTORS.get(_fold_unit(unit))
    if factor is None:
        raise UnitConversionError(
            f"Unidad desconocida: {unit!r} (validas: {', '.join(sorted(_BASE_FACTORS))})"
        )
    return qty * factor


def unit_family(unit: str) -> str:
    family = _UNIT_FAMILY.get(_fold_unit(unit))
    if family is None:
        raise UnitConversionError(
            f"Unidad desconocida: {unit!r} (validas: {', '.join(sorted(_UNIT_FAMILY))})"
        )
    return family


def cost_of_quantity(
    qty: Decimal,
    qty_unit: str,
    price_per_purchase_unit: Decimal,
    purchase_unit: str,
) -> Decimal:
    """Costo de `qty` (en unidades de receta) cuando el precio se da por unidad de compra.

    Las unidades deben pertenecer a la misma familia: peso (g/kg),
    volumen (ml/l) o unidad. Ej: 250g a $2.800/kg = $700.00.
    """
    if qty < 0:
        raise ValueError(f"qty no puede ser negativa: {qty}")
    if price_per_purchase_unit < 0:
        raise ValueError(
            f"price_per_purchase_unit no puede ser negativo: {price_per_purchase_unit}"
        )
    if unit_family(qty_unit) != unit_family(purchase_unit):
        raise UnitConversionError(
            f"No se puede costear {qty_unit} (familia {unit_family(qty_unit)}) "
            f"contra compra en {purchase_unit} (familia {unit_family(purchase_unit)})"
        )
    base_qty = to_base_units(qty, qty_unit)
    base_price = price_per_purchase_unit / to_base_units(Decimal("1"), purchase_unit)
    return (base_qty * base_price).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PricingSettings:
    """Parametros de la formula: valor hora, margen, redondeo e inclusiones."""

    hourly_rate: Decimal
    margin_pct: Decimal
    round_step: Decimal
    include_labor: bool = True
    include_gas: bool = False
    gas_pct: Decimal = Decimal("0")
    include_waste: bool = False
    waste_pct: Decimal = Decimal("0")

    def __post_init__(self):
        if self.hourly_rate < 0:
            raise ValueError(f"hourly_rate no puede ser negativo: {self.hourly_rate}")
        if not Decimal("0") <= self.margin_pct <= Decimal("200"):
            raise ValueError(f"margin_pct fuera de rango 0-200: {self.margin_pct}")
        if self.round_step <= 0:
            raise ValueError(f"round_step debe ser mayor que cero: {self.round_step}")
        if self.gas_pct < 0:
            raise ValueError(f"gas_pct no puede ser negativo: {self.gas_pct}")
        if self.waste_pct < 0:
            raise ValueError(f"waste_pct no puede ser negativo: {self.waste_pct}")


@dataclass(frozen=True)
class CostBreakdown:
    materials: Decimal
    waste: Decimal
    materials_con_merma: Decimal
    labor: Decimal
    gas: Decimal
    base: Decimal
    margin_pct: Decimal
    final: Decimal
    rounded: Decimal


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Valor al multiplo del paso mas cercano, modo HALF_UP."""
    if step <= 0:
        raise ValueError(f"round_step debe ser mayor que cero: {step}")
    return (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def calculate_price(
    line_items: Sequence[tuple[Decimal, str, Decimal, str]],
    prep_minutes: int | Decimal,
    settings: PricingSettings,
) -> CostBreakdown:
    """Aplica la formula del plan (master_plan.md §1.3).

    line_items: (qty, qty_unit, price_per_purchase_unit, purchase_unit).
    """
    if prep_minutes < 0:
        raise ValueError(f"prep_minutes no puede ser negativa: {prep_minutes}")

    materials = sum((cost_of_quantity(*item) for item in line_items), Decimal("0.00"))

    if settings.include_waste:
        materials_con_merma = (
            materials * (Decimal("100") + settings.waste_pct) / Decimal("100")
        ).quantize(_CENT, rounding=ROUND_HALF_UP)
    else:
        materials_con_merma = materials
    waste = materials_con_merma - materials

    if settings.include_labor:
        labor = (
            Decimal(prep_minutes) / Decimal("60") * settings.hourly_rate
        ).quantize(_CENT, rounding=ROUND_HALF_UP)
    else:
        labor = Decimal("0.00")

    if settings.include_gas:
        gas = (materials_con_merma * settings.gas_pct / Decimal("100")).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    else:
        gas = Decimal("0")

    base = materials_con_merma + labor + gas
    final = (base * (Decimal("100") + settings.margin_pct) / Decimal("100")).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    rounded = round_to_step(final, settings.round_step)

    return CostBreakdown(
        materials=materials,
        waste=waste,
        materials_con_merma=materials_con_merma,
        labor=labor,
        gas=gas,
        base=base,
        margin_pct=settings.margin_pct,
        final=final,
        rounded=rounded,
    )

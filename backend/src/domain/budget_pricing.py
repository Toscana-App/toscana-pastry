"""Costo por unidad de producto para presupuestos (Fase 7).

El presupuesto necesita el COSTO (sin margen) de 1 unidad del producto a
sus porciones estandar: se reutiliza el motor de precios (Fase 5) con
qty=1 y portions=servings (factor de escala 1) y se toma `base`
(materiales+merma+mano de obra+gas, antes del margen).

Producto incompleto (insumos sin precio): costo 0 en esas lineas,
misma decision que la Fase 6 (el snapshot de pedido la marca "missing";
el presupuesto no lleva esa granularidad, el costo queda parcial).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from domain.models import BusinessSettings, Ingredient, Product
from domain.pricing import calculate_price

_CENT = Decimal("0.01")


def _has_price(ingredient) -> bool:
    """Misma regla que Fase 5/6: no existe, borrado o precio 0 = sin
    precio (0 = sin precio, decision de negocio Fase 5)."""
    return (
        ingredient is not None
        and ingredient.deleted_at is None
        and ingredient.price_per_unit > 0
    )


def unit_product_cost(
    product: Product,
    ingredients_by_id: Dict[str, Ingredient],
    settings: BusinessSettings,
) -> Decimal:
    """Costo de 1 unidad del producto a porciones estandar (sin margen).
    Redondeado a centavos (ROUND_HALF_UP)."""
    line_items = []
    for item in product.recipe:
        ingredient = ingredients_by_id.get(item.ingredient_id)
        price = (
            ingredient.price_per_unit if _has_price(ingredient) else Decimal("0")
        )
        unit = item.unit
        if ingredient is not None:
            unit = ingredient.unit
        line_items.append((Decimal(item.qty), item.unit, price, unit))

    breakdown = calculate_price(
        line_items,
        Decimal(product.prep_time_min),
        settings.to_pricing(),
    )
    return breakdown.base.quantize(_CENT, rounding=ROUND_HALF_UP)

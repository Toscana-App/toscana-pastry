"""Derivacion de precio de producto (P3/P4, Fase 5).

Complemento puro de `pricing.py`: toma la receta y los insumos actuales y
devuelve o bien el desglose completo (producto completo) o la lista de
insumos que faltan (producto incompleto). El precio NUNCA se persiste:
siempre se recalcula en lectura con los datos corrientes (RF-P3-04).

Un insumo "no tiene precio" cuando: no existe, esta borrado suave, o su
price_per_unit es 0 (decision de negocio Fase 5: 0 = sin precio).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, Sequence

from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.pricing import CostBreakdown, calculate_price, cost_of_quantity

_CENT = Decimal("0.01")


def _has_price(ingredient: Optional[Ingredient]) -> bool:
    return (
        ingredient is not None
        and ingredient.deleted_at is None
        and ingredient.price_per_unit > 0
    )


@dataclass(frozen=True)
class ProductPrice:
    """Resultado de la derivacion.

    complete=True: breakdown y per_serving poblados, missing vacio.
    complete=False: breakdown/per_serving None, missing con los nombres
    de los insumos sin precio (orden de la receta, sin duplicados).
    """

    complete: bool
    missing: tuple
    breakdown: Optional[CostBreakdown]
    per_serving: Optional[Decimal]


def derive_product_price(
    product: Product,
    ingredients_by_id: Dict[str, Ingredient],
    settings: BusinessSettings,
) -> ProductPrice:
    missing: list = []
    seen_missing = set()
    for item in product.recipe:
        ingredient = ingredients_by_id.get(item.ingredient_id)
        if not _has_price(ingredient) and item.ingredient_id not in seen_missing:
            seen_missing.add(item.ingredient_id)
            missing.append(
                ingredient.name if ingredient is not None else "Insumo desconocido"
            )
    if missing:
        return ProductPrice(
            complete=False, missing=tuple(missing), breakdown=None, per_serving=None
        )

    line_items = [
        (
            item.qty,
            item.unit,
            ingredients_by_id[item.ingredient_id].price_per_unit,
            ingredients_by_id[item.ingredient_id].unit,
        )
        for item in product.recipe
    ]
    breakdown = calculate_price(line_items, product.prep_time_min, settings.to_pricing())
    per_serving = (breakdown.final / Decimal(product.servings)).quantize(
        _CENT, rounding=ROUND_HALF_UP
    )
    return ProductPrice(
        complete=True, missing=(), breakdown=breakdown, per_serving=per_serving
    )


def line_cost_of_item(
    item: RecipeItem, ingredients_by_id: Dict[str, Ingredient]
) -> Optional[Decimal]:
    """Costo de una linea de receta (tab Ingredientes del P4 §3).

    None cuando el insumo no existe, esta borrado o no tiene precio.
    """
    ingredient = ingredients_by_id.get(item.ingredient_id)
    if not _has_price(ingredient):
        return None
    return cost_of_quantity(
        item.qty, item.unit, ingredient.price_per_unit, ingredient.unit
    )

"""Pricing de items de pedido (Fase 6): calculo puro, sin I/O.

Reglas (decisiones de negocio confirmadas):

* Escala por porciones: factor = portions / servings del producto. Escala
  las cantidades de insumos y los minutos de mano de obra (la spec: "la
  conversion es en funcion de la cantidad de porciones que se pida").
* Margin por pedido: el override reemplaza el margen del tenant (no lo
  suma). Sin override = margin del tenant.
* Productos incompletos (insumos sin precio): entran al pedido con costo
  0 en esas lineas y el snapshot queda "parcial" (missing enumerado).
* `Order.total` = suma del `rounded` de cada item.

El motor `calculate_price` no se toca: se le pasa la receta ya escalada.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional, Tuple

from domain.models import BusinessSettings, Ingredient, Product, PricingSettings
from domain.orders import OrderItem, OrderItemSnapshot, OrderItemSnapshotLine
from domain.pricing import (
    CostBreakdown,
    UnitConversionError,
    calculate_price,
    cost_of_quantity,
    round_to_step,
)


def _has_price(ingredient: Optional[Ingredient]) -> bool:
    """Misma regla que Fase 5: no existe, borrado o precio 0 = sin precio
    (0 = sin precio, decision de negocio Fase 5)."""
    return (
        ingredient is not None
        and ingredient.deleted_at is None
        and ingredient.price_per_unit > 0
    )


def price_order_item(
    product: Product,
    ingredients_by_id: Dict[str, Ingredient],
    settings: BusinessSettings,
    qty: int,
    portions: int,
    margin_override: Optional[Decimal] = None,
) -> OrderItemSnapshot:
    """Desglose congelado de un item de pedido.

    `qty` = unidades del producto; `portions` = porciones solicitadas
    (el factor escala receta y mano de obra).
    """
    scale = Decimal(portions) / Decimal(product.servings)
    pricing = settings.to_pricing()
    if margin_override is not None:
        if not (Decimal("0") <= margin_override <= Decimal("200")):
            raise ValueError("El margen del pedido debe estar entre 0% y 200%")
        pricing = PricingSettings(
            hourly_rate=pricing.hourly_rate,
            margin_pct=margin_override,
            round_step=pricing.round_step,
            include_labor=pricing.include_labor,
            include_gas=pricing.include_gas,
            gas_pct=pricing.gas_pct,
            include_waste=pricing.include_waste,
            waste_pct=pricing.waste_pct,
        )

    line_items: list = []
    missing: list = []
    for item in product.recipe:
        ingredient = ingredients_by_id.get(item.ingredient_id)
        qty_unit = Decimal(item.qty) * scale * Decimal(qty)
        if _has_price(ingredient):
            line_items.append((qty_unit, item.unit, ingredient.price_per_unit, ingredient.unit))
        else:
            # Insumo sin precio: costo 0 y queda marcado (decisión P6).
            line_items.append((qty_unit, item.unit, Decimal("0"), item.unit))
            if ingredient is not None:
                missing.append(ingredient.name)
            else:
                missing.append(f"insumo borrado ({item.ingredient_id})")

    # Mano de obra escalada: minutos * factor de porciones * unidades.
    # calculate_price acepta Decimal (hace Decimal(prep_minutes) internamente).
    labor_minutes = Decimal(product.prep_time_min) * scale * Decimal(qty)

    breakdown: CostBreakdown = calculate_price(
        line_items, labor_minutes, pricing
    )

    lines: Tuple[OrderItemSnapshotLine, ...] = ()
    for item in product.recipe:
        ingredient = ingredients_by_id.get(item.ingredient_id)
        qty_scaled = Decimal(item.qty) * scale * Decimal(qty)
        if _has_price(ingredient):
            line_cost = cost_of_quantity(
                qty_scaled, item.unit, ingredient.price_per_unit, ingredient.unit
            )
        else:
            line_cost = Decimal("0")
        lines = lines + (
            OrderItemSnapshotLine(
                ingredient_id=item.ingredient_id,
                ingredient_name=ingredient.name if ingredient is not None
                else f"insumo borrado ({item.ingredient_id})",
                qty=qty_scaled,
                unit=item.unit,
                cost=line_cost,
                is_missing=not _has_price(ingredient),
            ),
        )

    return OrderItemSnapshot(
        lines=lines,
        materials=breakdown.materials,
        waste=breakdown.waste,
        materials_con_merma=breakdown.materials_con_merma,
        labor=breakdown.labor,
        gas=breakdown.gas,
        base=breakdown.base,
        margin_pct=pricing.margin_pct,
        final=breakdown.final,
        rounded=breakdown.rounded,
        missing=tuple(dict.fromkeys(missing)),
    )


def plan_order_deductions(
    snapshots: Dict[str, OrderItemSnapshot],
) -> Dict[str, Decimal]:
    """Agrega el stock a descontar por insumo al confirmar un pedido:
    suma las lineas del snapshot (lo que se cotizo, RNF-P6-03). Las lineas
    de insumos sin precio no descuentan stock."""
    deductions: Dict[str, Decimal] = {}
    for snapshot in snapshots.values():
        for line in snapshot.lines:
            if line.is_missing or line.qty <= 0:
                continue
            deductions[line.ingredient_id] = (
                deductions.get(line.ingredient_id, Decimal("0")) + line.qty
            )
    return deductions


def check_stock(
    deductions: Dict[str, Decimal],
    stock_by_id: Dict[str, Decimal],
) -> Dict[str, Decimal]:
    """Devuelve el shortage (insumo -> falta) para 409; vacio si alcanza.
    Puro: la toma de lock + la aplicacion la hace la capa de datos."""
    shortage: Dict[str, Decimal] = {}
    for ingredient_id, needed in deductions.items():
        available = stock_by_id.get(ingredient_id, Decimal("0"))
        if available < needed:
            shortage[ingredient_id] = needed - available
    return shortage

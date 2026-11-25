"""Efectos de stock del pedido (deducción al confirmar, restitución al cancelar).

Compartidos entre TransitionOrderStatus (O1) y los use cases de
comprobante (O5/S4). La decision de CUANDO aplica cada efecto vive en
el use case; este modulo solo aplica lo que se le instruye.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import TYPE_CHECKING, List, Tuple

from domain.models import Ingredient, StockMovement
from domain.order_pricing import check_stock, plan_order_deductions
from domain.orders import InsufficientOrderStockError
from domain.stock import apply_movement

if TYPE_CHECKING:
    from domain.order import Order
    from domain.orders import Order as P6Order
    from domain.repositories import OrderTransitionStore, ReceiptVerificationStore


async def deduct_order_stock(
    order: "Order | P6Order", store: "OrderTransitionStore | ReceiptVerificationStore"
) -> None:
    """Deduce el plan del pedido (efecto O1 al confirmar)."""
    deductions = plan_order_deductions(order.snapshots)
    ingredients = await store.lock_ingredients(list(deductions))

    available = {
        ingredient_id: (
            ingredients[ingredient_id].stock_qty
            if ingredient_id in ingredients
            else Decimal("0")
        )
        for ingredient_id in deductions
    }
    shortage = check_stock(deductions, available)
    if shortage:
        raise InsufficientOrderStockError(
            shortage,
            available={i: available[i] for i in shortage},
            required={i: deductions[i] for i in shortage},
        )

    changes: List[Tuple[Ingredient, StockMovement]] = []
    for ingredient_id, needed in deductions.items():
        updated, movement = apply_movement(
            ingredients[ingredient_id], -needed, reason="pedido", ref=order.id
        )
        changes.append(
            (updated, dataclasses.replace(movement, ingredient_id=ingredient_id))
        )
    await store.apply_movements(changes)


async def restore_order_stock(
    order: "Order | P6Order", store: "OrderTransitionStore | ReceiptVerificationStore"
) -> None:
    """Reintegra el plan del pedido (efecto O1 al cancelar)."""
    deductions = plan_order_deductions(order.snapshots)
    ingredients = await store.lock_ingredients(list(deductions))

    changes: List[Tuple[Ingredient, StockMovement]] = []
    for ingredient_id, needed in deductions.items():
        ingredient = ingredients.get(ingredient_id)
        if ingredient is None:
            continue
        updated, movement = apply_movement(
            ingredient, needed, reason="anulacion", ref=order.id
        )
        changes.append(
            (updated, dataclasses.replace(movement, ingredient_id=ingredient_id))
        )
    await store.apply_movements(changes)

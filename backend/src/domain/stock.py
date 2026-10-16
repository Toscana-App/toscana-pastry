"""Reglas puras de stock (sin I/O, testables al 100%).

Estados por spec p02 RF-P2-03: EMPTY (0), LOW (<= umbral), OK.
El stock nunca queda negativo: el ajuste que lo llevaría a negativo
es error de dominio (la API lo mapea a 400).
"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from domain.models import STOCK_REASONS, Ingredient, StockMovement, StockStatus


class InsufficientStockError(ValueError):
    """El ajuste llevaría el stock a un valor negativo."""


def stock_status(qty: Decimal, threshold: Decimal) -> StockStatus:
    """Estado derivado: no se guarda, se calcula (campo computado del
    servidor, security #8)."""
    if qty <= 0:
        return StockStatus.EMPTY
    if qty <= threshold:
        return StockStatus.LOW
    return StockStatus.OK


def apply_movement(
    ingredient: Ingredient,
    qty_delta: Decimal,
    reason: str,
    ref: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[Ingredient, StockMovement]:
    """Aplica un ajuste al stock y devuelve (nuevo ingrediente, movimiento).

    El ingrediente es inmutable: el llamador persiste el resultado con el
    mismo commit del movimiento (una operación atómica).
    """
    if reason not in STOCK_REASONS:
        raise ValueError(
            f"motivo invalido: {reason!r} (esperado: {', '.join(STOCK_REASONS)})"
        )
    if qty_delta == 0:
        raise ValueError("delta debe ser distinto de cero")
    new_qty = ingredient.stock_qty + qty_delta
    if new_qty < 0:
        raise InsufficientStockError(
            f"stock negativo: {ingredient.stock_qty} + ({qty_delta}) = {new_qty}"
        )
    movement = StockMovement(
        qty_delta=qty_delta,
        reason=reason,
        ref=ref,
        ingredient_id=ingredient.id,
        created_at=now or datetime.now(timezone.utc),
    )
    return replace(ingredient, stock_qty=new_qty), movement

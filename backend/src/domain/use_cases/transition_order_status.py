import dataclasses
from decimal import Decimal
from typing import List, Tuple

from domain.models import Ingredient, StockMovement
from domain.order_pricing import check_stock, plan_order_deductions
from domain.orders import (
    InsufficientOrderStockError,
    InvalidStatusTransitionError,
    Order,
    transition_status,
)
from domain.repositories import OrderTransitionStore
from domain.stock import apply_movement


class TransitionOrderStatus:
    """Orquesta una transicion de estado del pedido (RNF-P6-01/02/04).

    Las reglas viven aca: validar la transicion bajo lock, decidir si el
    stock alcanza, calcular movimientos. El repositorio solo aporta
    primitivas transaccionales (lock, aplicar movimientos, estado,
    commit/rollback). Orden de locks: pedido primero, insumos por id."""

    def __init__(self, store: OrderTransitionStore):
        self._store = store

    async def execute(self, order_id: str, target: str) -> Order:
        store = self._store
        try:
            order = await store.lock_order(order_id)
            if order is None:
                await store.rollback()
                raise InvalidStatusTransitionError("inexistente", target)
            try:
                transition_status(order.status, target)
            except InvalidStatusTransitionError:
                await store.rollback()
                raise

            if target == "confirmado":
                await self._deduct_stock(order)
            elif target == "cancelado":
                await self._restore_stock(order)

            await store.set_status(order.id, target)
            await store.commit()
            return dataclasses.replace(order, status=target)
        except (InsufficientOrderStockError, InvalidStatusTransitionError):
            raise
        except Exception:
            await store.rollback()
            raise

    async def _deduct_stock(self, order: Order) -> None:
        deductions = plan_order_deductions(order.snapshots)
        ingredients = await self._store.lock_ingredients(list(deductions))

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
            await self._store.rollback()
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
        await self._store.apply_movements(changes)

    async def _restore_stock(self, order: Order) -> None:
        deductions = plan_order_deductions(order.snapshots)
        ingredients = await self._store.lock_ingredients(list(deductions))

        changes: List[Tuple[Ingredient, StockMovement]] = []
        for ingredient_id, needed in deductions.items():
            ingredient = ingredients.get(ingredient_id)
            if ingredient is None:
                # Insumo borrado despues de confirmar: no hay saldo que
                # reponer (la decision de negocio lo permite).
                continue
            updated, movement = apply_movement(
                ingredient, needed, reason="anulacion", ref=order.id
            )
            changes.append(
                (updated, dataclasses.replace(movement, ingredient_id=ingredient_id))
            )
        await self._store.apply_movements(changes)

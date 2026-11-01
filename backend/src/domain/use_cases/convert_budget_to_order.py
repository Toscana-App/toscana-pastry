import dataclasses
import datetime
from dataclasses import dataclass
from typing import Dict, List

from domain.budgets import BudgetAlreadyConvertedError, BudgetNotConvertibleError
from domain.order_pricing import price_order_item
from domain.orders import Order, OrderItem, OrderItemSnapshot
from domain.repositories import (
    BudgetRepository,
    IngredientRepository,
    OrderRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases.derive_budget_items import load_ingredients, load_products
from domain.use_cases.get_settings import GetSettings


class BudgetNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class ConversionResult:
    order_id: str
    seq: str


class ConvertBudgetToOrder:
    """Convierte un presupuesto `enviado` en un pedido `nuevo` (RF-P8-08):
    mismo cliente e items, con SUS PROPIOS snapshots (RNF-P6-03) y el
    margen del presupuesto. Los precios manuales se copian al snapshot.
    El descuento de stock ocurre al confirmar el pedido, no aqui."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        order_repo: OrderRepository,
        product_repo: ProductRepository,
        ingredient_repo: IngredientRepository,
        settings_repo: SettingsRepository,
    ):
        self._budgets = budget_repo
        self._orders = order_repo
        self._products = product_repo
        self._ingredients = ingredient_repo
        self._settings = settings_repo

    async def execute(self, budget_id: str) -> ConversionResult:
        budget = await self._budgets.get(budget_id)
        if budget is None:
            raise BudgetNotFoundError(budget_id)
        if budget.order_id is not None:
            raise BudgetAlreadyConvertedError(budget_id)
        if budget.status != "enviado":
            raise BudgetNotConvertibleError(budget_id)
        settings = await GetSettings(self._settings).execute()
        products = await load_products(
            self._products, [item.product_id for item in budget.items]
        )
        ingredients_by_id = await load_ingredients(self._ingredients)
        order_items: List[OrderItem] = []
        snapshots: Dict[str, OrderItemSnapshot] = {}
        for item in budget.items:
            product = products[item.product_id]
            portions = product.servings
            snapshot = price_order_item(
                product,
                ingredients_by_id,
                settings,
                qty=item.qty,
                portions=portions,
                margin_override=budget.margin_pct,
            )
            if item.price_overridden:
                # Precio manual del presupuesto: el pedido lo respeta.
                snapshot = dataclasses.replace(
                    snapshot, final=item.line_selling, rounded=item.line_selling
                )
            order_item = OrderItem(
                product_id=product.id or "",
                qty=item.qty,
                portions=portions,
                note="",
                product_name=product.name,
            )
            order_items.append(order_item)
            snapshots[order_item.id or ""] = snapshot
        order = Order(
            customer_id=budget.customer_id,
            customer_name=budget.customer_name,
            customer_phone=budget.customer_phone,
            date=datetime.date.today(),
            margin_pct=budget.margin_pct,
            items=tuple(order_items),
            snapshots=snapshots,
        )
        created = await self._orders.create(order)
        # ponytail: si dos conversiones compiten, el UPDATE condicional deja
        # una sola ganadora; la perdedora ya creo un pedido huerfano (el
        # create del pedido hace commit propio). Ceiling: conversion
        # concurrente del mismo presupuesto.
        if not await self._budgets.mark_converted(budget_id, created.id or ""):
            raise BudgetAlreadyConvertedError(budget_id)
        return ConversionResult(order_id=created.id or "", seq=budget.seq)

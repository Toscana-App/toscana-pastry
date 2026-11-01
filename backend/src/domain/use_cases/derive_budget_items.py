from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from domain.budget_pricing import unit_product_cost
from domain.budgets import CalculationMode, derive_budget_items
from domain.models import BusinessSettings, Ingredient, Product
from domain.repositories import IngredientRepository, ProductRepository


class UnknownProductError(LookupError):
    """El producto no existe o fue eliminado."""

    def __init__(self, product_id: str):
        super().__init__(f"Producto desconocido o eliminado: {product_id}")
        self.product_id = product_id


@dataclass(frozen=True)
class BudgetItemDraft:
    """Entrada de un item: producto, cantidad y precio manual opcional
    (Decimal en unidades; la conversion desde centavos es del borde)."""

    product_id: str
    qty: int
    price_override: Optional[Decimal] = None


async def load_products(
    repo: ProductRepository, product_ids: List[str]
) -> Dict[str, Product]:
    by_id: Dict[str, Product] = {}
    for product_id in dict.fromkeys(product_ids):
        product = await repo.get(product_id)
        if product is None:
            raise UnknownProductError(product_id)
        by_id[product_id] = product
    return by_id


async def load_ingredients(repo: IngredientRepository) -> Dict[str, Ingredient]:
    """Insumos activos paginados (los borrados quedan con costo 0, mismo
    criterio que el pedido)."""
    by_id: Dict[str, Ingredient] = {}
    page = 1
    while True:
        items, total = await repo.list(None, None, page, 100)
        for item in items:
            by_id[item.id] = item
        if not items or len(by_id) >= total:
            break
        page += 1
    return by_id


class DeriveBudgetItems:
    """Deriva (items, margen aplicado) contra el catalogo corriente. El
    override de precio solo rige en modo manual (RF-P7-05)."""

    def __init__(
        self, product_repo: ProductRepository, ingredient_repo: IngredientRepository
    ):
        self._product_repo = product_repo
        self._ingredient_repo = ingredient_repo

    async def execute(
        self,
        settings: BusinessSettings,
        drafts: List[BudgetItemDraft],
        margin_override: Optional[Decimal],
        mode: CalculationMode,
    ) -> Tuple[list, Decimal]:
        products = await load_products(
            self._product_repo, [d.product_id for d in drafts]
        )
        ingredients_by_id = await load_ingredients(self._ingredient_repo)
        margin_applied = (
            margin_override if margin_override is not None else settings.margin_pct
        )
        raw = []
        for entry in drafts:
            product = products[entry.product_id]
            unit_cost = unit_product_cost(product, ingredients_by_id, settings)
            override = (
                entry.price_override
                if entry.price_override is not None and mode == CalculationMode.MANUAL
                else None
            )
            raw.append((entry.product_id, product.name, entry.qty, unit_cost, override))
        items, _totals = derive_budget_items(tuple(raw), margin_applied)
        return list(items), margin_applied

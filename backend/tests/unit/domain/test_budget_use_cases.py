"""Budget use cases (derive items, convert to order) against in-memory fakes."""
import dataclasses
from decimal import Decimal

import pytest

from domain.budgets import (
    Budget,
    BudgetAlreadyConvertedError,
    BudgetItem,
    BudgetNotConvertibleError,
    CalculationMode,
)
from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.use_cases import (
    BudgetItemDraft,
    BudgetNotFoundError,
    ConvertBudgetToOrder,
    DeriveBudgetItems,
    UnknownProductError,
)

pytestmark = pytest.mark.asyncio


def _settings() -> BusinessSettings:
    return BusinessSettings(
        hourly_rate=Decimal("150"), margin_pct=Decimal("100"), round_step=Decimal("5")
    )


def _flour() -> Ingredient:
    return Ingredient(
        name="Harina", unit="kg", price_per_unit=Decimal("2800"),
        stock_qty=Decimal("10"), id="flour",
    )


def _torta() -> Product:
    return Product(
        name="Torta", category="Tortas",
        recipe=(RecipeItem(ingredient_id="flour", qty=Decimal("250"), unit="g"),),
        prep_time_min=30, servings=6, id="torta",
    )


class FakeProducts:
    def __init__(self, *products):
        self._by_id = {p.id: p for p in products}

    async def get(self, product_id):
        return self._by_id.get(product_id)


class FakeIngredients:
    def __init__(self, *items):
        self._items = list(items)

    async def list(self, q, category, page, page_size):
        start = (page - 1) * page_size
        return self._items[start:start + page_size], len(self._items)


class FakeSettings:
    async def get(self):
        return _settings()


class FakeOrders:
    def __init__(self):
        self.created = []

    async def create(self, order):
        self.created.append(order)
        return dataclasses.replace(order, id=f"order-{len(self.created)}")


class FakeBudgets:
    def __init__(self, budget=None):
        self.budget = budget
        self.mark_result = True
        self.converted = []

    async def get(self, budget_id):
        return self.budget

    async def mark_converted(self, budget_id, order_id):
        self.converted.append((budget_id, order_id))
        return self.mark_result


def _budget(**overrides) -> Budget:
    item = BudgetItem(
        product_id="torta", product_name="Torta", qty=2,
        unit_cost=Decimal("775"), unit_selling=Decimal("1550"),
    )
    base = dict(
        customer_id="c1", customer_name="Maria", customer_phone="1",
        items=(item,), margin_pct=None, status="enviado", seq="#00001", id="b1",
    )
    base.update(overrides)
    return Budget(**base)


def _convert(budgets, orders=None):
    orders = orders or FakeOrders()
    return (
        ConvertBudgetToOrder(
            budgets, orders, FakeProducts(_torta()),
            FakeIngredients(_flour()), FakeSettings(),
        ),
        orders,
    )


class TestDeriveBudgetItems:
    def _use_case(self):
        return DeriveBudgetItems(FakeProducts(_torta()), FakeIngredients(_flour()))

    async def test_derives_cost_and_price_from_catalog(self):
        items, margin = await self._use_case().execute(
            _settings(), [BudgetItemDraft("torta", 2)], None, CalculationMode.COST_PLUS
        )
        assert margin == Decimal("100")
        assert items[0].unit_cost == Decimal("775")
        assert items[0].unit_selling == Decimal("1550")

    async def test_override_only_applies_in_manual_mode(self):
        draft = BudgetItemDraft("torta", 1, Decimal("2000"))
        manual, _ = await self._use_case().execute(
            _settings(), [draft], None, CalculationMode.MANUAL
        )
        cost_plus, _ = await self._use_case().execute(
            _settings(), [draft], None, CalculationMode.COST_PLUS
        )
        assert manual[0].unit_selling == Decimal("2000")
        assert manual[0].price_overridden is True
        assert cost_plus[0].unit_selling == Decimal("1550")

    async def test_margin_override_wins_over_tenant(self):
        _, margin = await self._use_case().execute(
            _settings(), [BudgetItemDraft("torta", 1)], Decimal("50"),
            CalculationMode.COST_PLUS,
        )
        assert margin == Decimal("50")

    async def test_unknown_product_raises(self):
        with pytest.raises(UnknownProductError, match="ghost"):
            await self._use_case().execute(
                _settings(), [BudgetItemDraft("ghost", 1)], None,
                CalculationMode.COST_PLUS,
            )


class TestConvertBudgetToOrder:
    async def test_creates_order_and_links_budget(self):
        budgets = FakeBudgets(_budget())
        use_case, orders = _convert(budgets)
        result = await use_case.execute("b1")
        assert result.seq == "#00001"
        assert result.order_id == "order-1"
        assert budgets.converted == [("b1", "order-1")]
        assert orders.created[0].customer_name == "Maria"

    async def test_manual_price_is_copied_to_the_snapshot(self):
        item = BudgetItem(
            product_id="torta", product_name="Torta", qty=2,
            unit_cost=Decimal("775"), unit_selling=Decimal("2000"),
            price_overridden=True,
        )
        use_case, orders = _convert(FakeBudgets(_budget(items=(item,))))
        await use_case.execute("b1")
        assert orders.created[0].total == Decimal("4000")

    async def test_catalog_price_is_used_without_override(self):
        use_case, orders = _convert(FakeBudgets(_budget()))
        await use_case.execute("b1")
        assert orders.created[0].total == Decimal("3100")

    async def test_missing_budget_raises_not_found(self):
        use_case, _ = _convert(FakeBudgets(None))
        with pytest.raises(BudgetNotFoundError):
            await use_case.execute("nope")

    async def test_draft_is_not_convertible(self):
        use_case, orders = _convert(FakeBudgets(_budget(status="borrador")))
        with pytest.raises(BudgetNotConvertibleError):
            await use_case.execute("b1")
        assert orders.created == []

    async def test_already_converted_creates_nothing(self):
        use_case, orders = _convert(FakeBudgets(_budget(order_id="order-9")))
        with pytest.raises(BudgetAlreadyConvertedError):
            await use_case.execute("b1")
        assert orders.created == []

    async def test_lost_race_on_link_raises_already_converted(self):
        budgets = FakeBudgets(_budget())
        budgets.mark_result = False
        use_case, _ = _convert(budgets)
        with pytest.raises(BudgetAlreadyConvertedError):
            await use_case.execute("b1")

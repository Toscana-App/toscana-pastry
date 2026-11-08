import datetime
from dataclasses import replace
from decimal import Decimal

import pytest

from domain.budgets import (
    BUDGET_STATUSES,
    Budget,
    BudgetItem,
    CalculationMode,
    NoBudgetChangesError,
    compute_totals,
    derive_budget_items,
    format_sequence,
    transition_to_sent,
    unit_selling_price,
)
from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.budget_pricing import unit_product_cost




def tenant(**overrides) -> BusinessSettings:
    base = dict(
        hourly_rate=Decimal("150"),
        margin_pct=Decimal("100"),
        round_step=Decimal("5"),
    )
    base.update(overrides)
    return BusinessSettings(**base)


def make_flour(price="2800") -> Ingredient:
    return Ingredient(
        name="Harina", unit="kg", price_per_unit=Decimal(price),
        stock_qty=Decimal("10"),
        id="flour",
    )


def make_torta() -> Product:
    return Product(
        name="Torta de Limón",
        category="Tortas",
        recipe=(RecipeItem(ingredient_id="flour", qty=Decimal("250"), unit="g"),),
        prep_time_min=30,
        servings=6,
        id="torta",
    )


def make_budget(**overrides) -> Budget:
    item = BudgetItem(
        product_id="torta",
        product_name="Torta de Limón",
        qty=2,
        unit_cost=Decimal("775"),
        unit_selling=Decimal("1550"),
    )
    base = dict(
        customer_id="c1",
        customer_name="María",
        customer_phone="3575551234",
        items=(item,),
        margin_pct=None,
        calculation_mode=CalculationMode.COST_PLUS,
    )
    base.update(overrides)
    return Budget(**base)




class TestUnitProductCost:
    def test_costo_sin_margen(self):
        product = make_torta()
        cost = unit_product_cost(product, {"flour": make_flour()}, tenant())
        assert cost == Decimal("775")

    def test_costo_segue_el_precio_del_insumo(self):
        product = make_torta()
        cost = unit_product_cost(
            product, {"flour": make_flour("5600")}, tenant()
        )
        assert cost == Decimal("1475")

    def test_insumo_sin_precio_aporta_cero(self):
        product = make_torta()
        cost = unit_product_cost(
            product, {"flour": make_flour("0")}, tenant()
        )
        assert cost == Decimal("75")




class TestDerive:
    def test_cost_plus_dobla_el_costo_con_margen_100(self):
        items, totals = derive_budget_items(
            (("torta", "Torta de Limón", 2, Decimal("775"), None),),
            Decimal("100"),
        )
        assert len(items) == 1
        item = items[0]
        assert item.unit_selling == Decimal("1550")
        assert item.price_overridden is False
        assert item.line_cost == Decimal("1550")
        assert item.line_selling == Decimal("3100")
        assert totals.subtotal == Decimal("3100")
        assert totals.total_costos == Decimal("1550")
        assert totals.ganancia == Decimal("1550")
        assert totals.total_venta == Decimal("3100")
        assert totals.iva == Decimal("651")

    def test_margen_cero_precio_igual_al_costo(self):
        items, _ = derive_budget_items(
            (("torta", "Torta", 1, Decimal("775"), None),), Decimal("0")
        )
        assert items[0].unit_selling == Decimal("775")

    def test_manual_con_override_ignora_el_margen(self):
        items, totals = derive_budget_items(
            (("torta", "Torta", 1, Decimal("775"), Decimal("500")),),
            Decimal("100"),
        )
        assert items[0].unit_selling == Decimal("500")
        assert items[0].price_overridden is True
        assert totals.ganancia == Decimal("-275")
        assert totals.total_venta == Decimal("500")
        assert totals.iva == Decimal("105")

    def test_manual_sin_override_usa_cost_plus(self):
        items, _ = derive_budget_items(
            (("torta", "Torta", 1, Decimal("775"), None),), Decimal("50")
        )
        assert items[0].unit_selling == Decimal("1162.50")
        assert items[0].price_overridden is False

    def test_margen_fuera_de_rango_da_error(self):
        with pytest.raises(ValueError):
            derive_budget_items(
                (("torta", "Torta", 1, Decimal("775"), None),), Decimal("201")
            )
        with pytest.raises(ValueError):
            derive_budget_items(
                (("torta", "Torta", 1, Decimal("775"), None),), Decimal("-1")
            )

    def test_override_negativo_da_error(self):
        with pytest.raises(ValueError):
            unit_selling_price(Decimal("775"), Decimal("100"), Decimal("-1"))

    def test_qty_invalido_da_error(self):
        with pytest.raises(ValueError):
            BudgetItem(
                product_id="t", product_name="T", qty=0,
                unit_cost=Decimal("1"), unit_selling=Decimal("2"),
            )

    def test_totales_vacios(self):
        totals = compute_totals(())
        assert totals.subtotal == Decimal("0")
        assert totals.ganancia == Decimal("0")




class TestStateMachine:
    def test_borrador_a_enviado_crea_version_1(self):
        budget = make_budget()
        assert budget.status == "borrador"
        assert budget.version == 0
        sent = transition_to_sent(budget)
        assert sent.status == "enviado"
        assert sent.version == 1
        assert sent.sent_at is not None
        assert budget.status == "borrador"

    def test_reenviar_sin_cambios_da_error(self):
        sent = transition_to_sent(make_budget())
        with pytest.raises(NoBudgetChangesError):
            transition_to_sent(sent)

    def test_reenviar_con_cambios_crea_version_nueva(self):
        sent = transition_to_sent(make_budget())
        edited = replace(sent, updated_at=sent.sent_at + datetime.timedelta(seconds=1))
        resent = transition_to_sent(edited)
        assert resent.version == 2
        assert resent.status == "enviado"

    def test_estado_invalido_rechazado(self):
        with pytest.raises(ValueError):
            make_budget(status="vuelto")
        assert BUDGET_STATUSES == ("borrador", "enviado")

    def test_items_vacios_rechazados(self):
        with pytest.raises(ValueError):
            Budget(
                customer_id="c", customer_name="C", customer_phone="1",
                items=(), margin_pct=None,
            )




class TestSequence:
    def test_formato(self):
        assert format_sequence(1) == "#00001"
        assert format_sequence(42) == "#00042"
        assert format_sequence(12345) == "#12345"

    def test_cero_rechazado(self):
        with pytest.raises(ValueError):
            format_sequence(0)

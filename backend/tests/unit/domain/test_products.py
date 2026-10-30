from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.pricing import cost_of_quantity, unit_family
from domain.product_price import derive_product_price, line_cost_of_item


def _settings(**overrides):
    base: dict[str, Decimal | bool] = dict(
        hourly_rate=Decimal("3000"),
        margin_pct=Decimal("30"),
        round_step=Decimal("100"),
        include_labor=True,
        include_gas=True,
        gas_pct=Decimal("3"),
        include_waste=True,
        waste_pct=Decimal("3"),
    )
    base.update(overrides)
    return BusinessSettings(**base)


def _ingredient(name="Harina", unit="kg", price="2800", deleted=False):
    return Ingredient(
        name=name,
        unit=unit,
        price_per_unit=Decimal(price),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )


def _recipe_item(ingredient_id="ing-1", qty="250", unit="g"):
    return RecipeItem(ingredient_id=ingredient_id, qty=Decimal(qty), unit=unit)


def _product(recipe, **overrides):
    base = dict(
        name="Torta de Limón",
        category="Tortas",
        description="",
        prep_time_min=30,
        servings=1,
        difficulty="simple",
    )
    base.update(overrides)
    return Product(recipe=tuple(recipe), **base)


# --- Validaciones de dominio ---------------------------------------------


def test_product_minimal_ok():
    product = _product([_recipe_item()])
    assert product.name == "Torta de Limón"
    assert len(product.recipe) == 1


def test_product_name_too_short_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], name="T")


def test_product_name_too_long_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], name="x" * 121)


def test_product_category_required():
    with pytest.raises(ValueError):
        _product([_recipe_item()], category="   ")


def test_product_category_too_long_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], category="c" * 61)


def test_product_description_too_long_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], description="d" * 501)


def test_product_prep_out_of_range_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], prep_time_min=1441)


@pytest.mark.parametrize("servings", [0, 1000])
def test_product_servings_out_of_range_raises(servings):
    with pytest.raises(ValueError):
        _product([_recipe_item()], servings=servings)


def test_product_difficulty_invalid_raises():
    with pytest.raises(ValueError):
        _product([_recipe_item()], difficulty="facil")


def test_product_empty_recipe_raises():
    with pytest.raises(ValueError):
        _product([])


def test_product_duplicate_ingredient_raises():
    with pytest.raises(ValueError):
        _product(
            [
                _recipe_item(ingredient_id="a", qty="1", unit="g"),
                _recipe_item(ingredient_id="a", qty="2", unit="g"),
            ]
        )


@pytest.mark.parametrize("qty", ["0", "-1"])
def test_recipe_item_qty_must_be_positive(qty):
    with pytest.raises(ValueError):
        _recipe_item(qty=qty)


def test_recipe_item_invalid_unit_raises():
    with pytest.raises(ValueError):
        _recipe_item(unit="onza")


# --- Derivación de precio --------------------------------------------------


def test_derive_complete_product():
    ingredients = {
        "harina": _ingredient("Harina", "kg", "2800"),
        "leche": _ingredient("Leche", "L", "1200"),
    }
    product = _product(
        [
            _recipe_item("harina", "250", "g"),
            _recipe_item("leche", "200", "ml"),
        ],
        servings=2,
    )
    price = derive_product_price(product, ingredients, _settings())
    assert price.complete is True
    assert price.missing == ()
    # 250 g @ 2800/kg = 700 + 200 ml @ 1200/l = 240 → 940
    assert price.breakdown.materials == Decimal("940.00")
    # merma 3% → 968.20; mano de obra 30 min @ 3000/h = 1500;
    # gas 3% de 968.20 = 29.05 → base 2497.25; margen 30% → 3246.43
    assert price.breakdown.materials_con_merma == Decimal("968.20")
    assert price.breakdown.labor == Decimal("1500.00")
    assert price.breakdown.base == Decimal("2497.25")
    assert price.breakdown.final == Decimal("3246.43")
    assert price.breakdown.rounded == Decimal("3200")
    # 3246.43 / 2 = 1623.215 → 1623.22 (ROUND_HALF_UP)
    assert price.per_serving == Decimal("1623.22")


def test_derive_incomplete_when_price_zero():
    ingredients = {"harina": _ingredient("Harina", "kg", "0")}
    product = _product([_recipe_item("harina")])
    price = derive_product_price(product, ingredients, _settings())
    assert price.complete is False
    assert price.missing == ("Harina",)
    assert price.breakdown is None
    assert price.per_serving is None


def test_derive_incomplete_when_ingredient_deleted():
    ingredients = {"harina": _ingredient("Harina", "kg", "2800", deleted=True)}
    product = _product([_recipe_item("harina")])
    price = derive_product_price(product, ingredients, _settings())
    assert price.complete is False
    assert price.missing == ("Harina",)


def test_derive_incomplete_when_ingredient_unknown():
    product = _product([_recipe_item("no-existe")])
    price = derive_product_price(product, {}, _settings())
    assert price.complete is False
    assert price.missing == ("Insumo desconocido",)


def test_derive_missing_dedupes_and_keeps_recipe_order():
    ingredients = {}
    # El dominio rechaza insumos duplicados; se prueba la dedup a nivel de
    # derivacion construyendo la receta sin la validacion.
    recipe = tuple(
        RecipeItem(ingredient_id=r.ingredient_id, qty=r.qty, unit=r.unit)
        for r in (
            RecipeItem(ingredient_id="a", qty=Decimal("1"), unit="g"),
            RecipeItem(ingredient_id="b", qty=Decimal("2"), unit="g"),
        )
    )
    product = Product(
        name="Producto", category="C", recipe=recipe, prep_time_min=0, servings=1
    )
    price = derive_product_price(product, {}, _settings())
    assert price.missing == ("Insumo desconocido", "Insumo desconocido")


def test_line_cost():
    ingredients = {"harina": _ingredient("Harina", "kg", "2800")}
    assert (
        line_cost_of_item(_recipe_item("harina"), ingredients)
        == Decimal("700.00")
    )
    assert line_cost_of_item(_recipe_item("no-existe"), ingredients) is None
    zero = {"harina": _ingredient("Harina", "kg", "0")}
    assert line_cost_of_item(_recipe_item("harina"), zero) is None


# --- Motor: "L" mayuscula equivale a "l" (fix de contrato Fase 5) -----------


def test_engine_accepts_uppercase_L():
    assert cost_of_quantity(Decimal("1.5"), "L", Decimal("1200"), "l") == Decimal(
        "1800.00"
    )
    assert cost_of_quantity(Decimal("250"), "g", Decimal("2800"), "kg") == Decimal(
        "700.00"
    )


def test_unit_family_accepts_uppercase_L():
    assert unit_family("L") == "volumen"
    assert unit_family("l") == "volumen"

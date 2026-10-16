"""Reglas puras de stock (spec p02 RF-P2-03, casos límite de la spec de tests)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from domain.models import Ingredient
from domain.stock import InsufficientStockError, apply_movement, stock_status


def _ingredient(qty="0", threshold="0"):
    return Ingredient(
        name="Harina 0000",
        unit="kg",
        price_per_unit=Decimal("2800"),
        stock_qty=Decimal(qty),
        low_stock_threshold=Decimal(threshold),
    )


# --- Estados (RF-P2-03) -------------------------------------------------


def test_status_empty_when_zero():
    assert stock_status(Decimal("0"), Decimal("5")) is _empty()


def test_status_empty_wins_over_threshold():
    # Umbral alto no vuelve LOW a un stock a cero: EMPTY.
    assert stock_status(Decimal("0"), Decimal("100")) is _empty()


def test_status_low_below_threshold():
    assert stock_status(Decimal("2"), Decimal("5")) is _low()


def test_status_low_at_exact_threshold():
    # "2 kg restantes" (umbral bajo) de la app original: <= incluye el borde.
    assert stock_status(Decimal("5"), Decimal("5")) is _low()


def test_status_ok_above_threshold():
    assert stock_status(Decimal("8"), Decimal("5")) is _ok()


def test_status_ok_with_zero_threshold():
    # Umbral 0: cualquier cantidad positiva es OK.
    assert stock_status(Decimal("1"), Decimal("0")) is _ok()


def _empty():
    from domain.models import StockStatus

    return StockStatus.EMPTY


def _low():
    from domain.models import StockStatus

    return StockStatus.LOW


def _ok():
    from domain.models import StockStatus

    return StockStatus.OK


# --- Movimientos (RF-P2-04) ---------------------------------------------


def test_apply_positive_movement():
    ingredient = _ingredient(qty="10")
    updated, movement = apply_movement(ingredient, Decimal("5"), "compra", ref="pedido 42")
    assert updated.stock_qty == Decimal("15")
    assert movement.qty_delta == Decimal("5")
    assert movement.reason == "compra"
    assert movement.ref == "pedido 42"
    assert movement.ingredient_id == ingredient.id


def test_apply_negative_movement():
    ingredient = _ingredient(qty="10")
    updated, _ = apply_movement(ingredient, Decimal("-3"), "merma")
    assert updated.stock_qty == Decimal("7")


def test_apply_movement_down_to_zero_is_allowed():
    # Vaciar el stock es legitimo (estado EMPTY); lo que no es negativo.
    ingredient = _ingredient(qty="5")
    updated, _ = apply_movement(ingredient, Decimal("-5"), "ajuste")
    assert updated.stock_qty == Decimal("0")
    assert stock_status(updated.stock_qty, updated.low_stock_threshold) is _empty()


def test_apply_movement_below_zero_raises():
    ingredient = _ingredient(qty="5")
    with pytest.raises(InsufficientStockError):
        apply_movement(ingredient, Decimal("-6"), "merma")


def test_apply_movement_zero_delta_raises():
    ingredient = _ingredient(qty="5")
    with pytest.raises(ValueError):
        apply_movement(ingredient, Decimal("0"), "compra")


def test_apply_movement_invalid_reason_raises():
    ingredient = _ingredient(qty="5")
    with pytest.raises(ValueError):
        apply_movement(ingredient, Decimal("1"), "donacion")


def test_apply_movement_does_not_mutate_original():
    # Entidad inmutable: el llamador decide persistir, no el dominio.
    ingredient = _ingredient(qty="10")
    apply_movement(ingredient, Decimal("5"), "compra")
    assert ingredient.stock_qty == Decimal("10")


def test_apply_movement_sets_utc_timestamp():
    ingredient = _ingredient()
    _, movement = apply_movement(ingredient, Decimal("1"), "compra")
    assert movement.created_at.tzinfo is not None
    now = datetime.now(timezone.utc)
    assert abs((now - movement.created_at).total_seconds()) < 5

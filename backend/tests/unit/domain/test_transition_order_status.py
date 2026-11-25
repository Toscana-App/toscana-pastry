import dataclasses
import datetime
from decimal import Decimal

import pytest

from domain.models import Ingredient
from domain.order_states import InvalidStatusTransitionError
from domain.orders import (
    InsufficientOrderStockError,
    Order,
    OrderItemSnapshot,
    OrderItemSnapshotLine,
)
from domain.use_cases.transition_order_status import TransitionOrderStatus


def _snapshot(*lines) -> OrderItemSnapshot:
    return OrderItemSnapshot(
        lines=tuple(
            OrderItemSnapshotLine(
                ingredient_id=i, ingredient_name=i, qty=Decimal(q), unit="g", cost=Decimal("0")
            )
            for i, q in lines
        )
    )


def _order(status="new", lines=(("flour", "500"),)) -> Order:
    return Order(
        customer_id="c1",
        customer_name="Ana",
        customer_phone="1",
        date=datetime.date(2026, 1, 1),
        status=status,
        id="o1",
        snapshots={"item1": _snapshot(*lines)},
    )


def _ing(id_, stock) -> Ingredient:
    return Ingredient(
        name=id_, unit="g", price_per_unit=Decimal("1"), stock_qty=Decimal(stock), id=id_
    )


class FakeStore:
    def __init__(self, order, ingredients):
        self.order = order
        self.ingredients = {i.id: i for i in ingredients}
        self.movements = []
        self.calls = []
        self.committed = False
        self.rolled_back = False

    async def lock_order(self, order_id):
        self.calls.append("lock_order")
        return self.order

    async def lock_ingredients(self, ids):
        self.calls.append(("lock_ingredients", list(ids)))
        return {i: self.ingredients[i] for i in ids if i in self.ingredients}

    async def apply_movements(self, changes):
        self.calls.append("apply_movements")
        for updated, movement in changes:
            self.ingredients[updated.id] = updated
            self.movements.append(movement)

    async def set_status(self, order_id, status):
        self.calls.append("set_status")
        self.order = dataclasses.replace(self.order, status=status)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


async def test_confirm_deducts_stock_and_sets_status():
    store = FakeStore(_order(), [_ing("flour", "1000")])
    result = await TransitionOrderStatus(store).execute("o1", "confirmed")

    assert result.status == "confirmed"
    assert store.ingredients["flour"].stock_qty == Decimal("500")
    assert [(m.reason, m.qty_delta, m.ref, m.ingredient_id) for m in store.movements] == [
        ("pedido", Decimal("-500"), "o1", "flour")
    ]
    assert store.committed and not store.rolled_back
    assert store.calls[0] == "lock_order"


async def test_confirm_insufficient_stock_rolls_back_with_available_and_required():
    store = FakeStore(_order(), [_ing("flour", "200")])
    with pytest.raises(InsufficientOrderStockError) as exc:
        await TransitionOrderStatus(store).execute("o1", "confirmed")

    assert exc.value.shortage == {"flour": Decimal("300")}
    assert exc.value.available == {"flour": Decimal("200")}
    assert exc.value.required == {"flour": Decimal("500")}
    assert store.rolled_back and not store.committed
    assert store.movements == []
    assert "set_status" not in store.calls


async def test_confirm_missing_ingredient_counts_as_zero_available():
    store = FakeStore(_order(), [])
    with pytest.raises(InsufficientOrderStockError) as exc:
        await TransitionOrderStatus(store).execute("o1", "confirmed")
    assert exc.value.available == {"flour": Decimal("0")}


async def test_cancel_restores_stock_and_skips_deleted_ingredient():
    store = FakeStore(
        _order("confirmed", lines=(("flour", "500"), ("gone", "10"))),
        [_ing("flour", "100")],
    )
    result = await TransitionOrderStatus(store).execute("o1", "cancelled")

    assert result.status == "cancelled"
    assert store.ingredients["flour"].stock_qty == Decimal("600")
    assert [(m.reason, m.ingredient_id) for m in store.movements] == [
        ("anulacion", "flour")
    ]
    assert store.committed


async def test_deliver_has_no_stock_effect():
    store = FakeStore(_order("pending_delivery"), [_ing("flour", "100")])
    result = await TransitionOrderStatus(store).execute("o1", "delivered")

    assert result.status == "delivered"
    assert store.movements == []
    assert not any(c == "apply_movements" for c in store.calls)
    assert store.committed


async def test_prepare_to_pending_delivery_has_no_stock_effect():
    store = FakeStore(_order("preparing"), [_ing("flour", "100")])
    result = await TransitionOrderStatus(store).execute("o1", "pending_delivery")

    assert result.status == "pending_delivery"
    assert store.movements == []
    assert not any(c == "apply_movements" for c in store.calls)
    assert store.committed


async def test_cancel_from_preparing_restores_stock():
    store = FakeStore(_order("preparing", lines=(("flour", "500"),)), [_ing("flour", "100")])
    result = await TransitionOrderStatus(store).execute("o1", "cancelled")

    assert result.status == "cancelled"
    assert store.ingredients["flour"].stock_qty == Decimal("600")
    assert [(m.reason, m.ingredient_id) for m in store.movements] == [
        ("anulacion", "flour")
    ]
    assert store.committed


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("confirmed", "confirmed"),
        ("cancelled", "delivered"),
        ("new", "delivered"),
        ("preparing", "delivered"),
    ],
)
async def test_invalid_transition_revalidated_under_lock(current, target):
    store = FakeStore(_order(current), [_ing("flour", "1000")])
    with pytest.raises(InvalidStatusTransitionError):
        await TransitionOrderStatus(store).execute("o1", target)
    assert store.rolled_back and not store.committed
    assert store.movements == []


async def test_cancel_from_new_has_no_stock_effect():
    store = FakeStore(_order("new"), [_ing("flour", "100")])
    result = await TransitionOrderStatus(store).execute("o1", "cancelled")

    assert result.status == "cancelled"
    assert store.ingredients["flour"].stock_qty == Decimal("100")
    assert store.movements == []
    assert not any(c == "apply_movements" for c in store.calls)
    assert store.committed


async def test_missing_order_is_invalid_transition():
    store = FakeStore(None, [])
    with pytest.raises(InvalidStatusTransitionError) as exc:
        await TransitionOrderStatus(store).execute("o1", "confirmed")
    assert exc.value.current == "inexistente"
    assert store.rolled_back


async def test_unexpected_error_rolls_back_and_propagates():
    store = FakeStore(_order(), [_ing("flour", "1000")])

    async def boom(order_id, status):
        raise RuntimeError("db down")

    store.set_status = boom
    with pytest.raises(RuntimeError):
        await TransitionOrderStatus(store).execute("o1", "confirmed")
    assert store.rolled_back and not store.committed

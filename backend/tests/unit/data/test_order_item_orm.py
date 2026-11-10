import pytest

from data.models import OrderItemORM


def test_order_item_orm_keeps_canonical_quantity_column() -> None:
    assert "quantity" in OrderItemORM.__table__.columns


def test_order_item_orm_has_no_redundant_qty_column() -> None:
    assert "qty" not in OrderItemORM.__table__.columns


def test_order_item_orm_rejects_qty_kwarg() -> None:
    with pytest.raises(TypeError):
        OrderItemORM(qty=2)  # type: ignore[call-arg]

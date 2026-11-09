
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from domain.coupon import Coupon
from domain.pricing import round_to_step

MAX_CART_LINES = 50
MIN_QTY = 1
MAX_QTY = 999

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class CartLine:

    product_id: str
    product_name: str
    unit_price: Decimal
    qty: int

    @property
    def total(self) -> Decimal:
        return (self.unit_price * self.qty).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class CartTotals:

    subtotal: Decimal
    discount_amount: Decimal
    final: Decimal


def compute_discount(
    total: Decimal, coupon: Coupon | None
) -> Decimal:
    if coupon is None:
        return Decimal("0.00")
    if coupon.type == "percent":
        return (total * coupon.value / _HUNDRED).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )
    return min(coupon.value, total).quantize(_CENT, rounding=ROUND_HALF_UP)


def cart_totals(
    lines: list[CartLine],
    coupon: Coupon | None,
    round_step: Decimal,
) -> CartTotals:
    subtotal = sum((line.total for line in lines), Decimal("0.00"))
    discount = compute_discount(subtotal, coupon)
    final = round_to_step(subtotal - discount, round_step)
    return CartTotals(
        subtotal=subtotal,
        discount_amount=discount,
        final=final,
    )


def _naive_utc(
    dt: datetime.datetime | None,
) -> datetime.datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.UTC).replace(tzinfo=None)
    return dt


def validate_coupon_for_cart(
    coupon: Coupon, now: datetime.datetime
) -> str | None:
    if coupon.status != "active":
        return "coupon_inactive"
    valid_from = _naive_utc(coupon.valid_from)
    valid_until = _naive_utc(coupon.valid_until)
    now_naive = _naive_utc(now)
    assert now_naive is not None
    if valid_from is not None and now_naive < valid_from:
        return "coupon_inactive"
    if valid_until is not None and now_naive > valid_until:
        return "coupon_expired"
    if coupon.max_uses is not None and coupon.uses >= coupon.max_uses:
        return "coupon_limit_reached"
    return None

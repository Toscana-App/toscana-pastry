"""Unit tests for the cart domain (RF-P11-03/14, C4).

Pure module: line totals, discount (percent/fixed, capped at total),
rounding after discount, coupon window/uses validation, limits.
"""

import datetime
from decimal import Decimal

import pytest

from domain.cart import (
    MAX_CART_LINES,
    MAX_QTY,
    MIN_QTY,
    CartLine,
    cart_totals,
    compute_discount,
    validate_coupon_for_cart,
)
from domain.coupon import Coupon


def _coupon(**overrides: object) -> Coupon:
    base: dict[str, object] = {
        "code": "VERANO10",
        "type": "percent",
        "value": Decimal(10),
    }
    base.update(overrides)  # type: ignore[arg-type]
    return Coupon(**base)  # type: ignore[arg-type]


# ─── Limits ───────────────────────────────────────────────────────────

class TestLimits:
    def test_qty_bounds(self):
        assert MIN_QTY == 1
        assert MAX_QTY == 999

    def test_max_lines(self):
        assert MAX_CART_LINES == 50


# ─── Line totals ──────────────────────────────────────────────────────

class TestCartTotals:
    def test_subtotal_sums_lines(self):
        lines = [
            CartLine(product_id="p1", product_name="Torta", unit_price=Decimal("1000.00"), qty=2),
            CartLine(product_id="p2", product_name="Alfajor", unit_price=Decimal("250.00"), qty=3),
        ]
        totals = cart_totals(lines, None, Decimal("0.01"))
        assert totals.subtotal == Decimal("2750.00")
        assert totals.discount_amount == Decimal("0.00")

    def test_empty_cart(self):
        totals = cart_totals([], None, Decimal("0.01"))
        assert totals.subtotal == Decimal(0)
        assert totals.discount_amount == Decimal(0)
        assert totals.final == Decimal(0)

    def test_final_rounded_to_step(self):
        # subtotal 2750, no coupon → round to step 100 → 2800 (HALF_UP)
        lines = [
            CartLine(product_id="p1", product_name="Torta", unit_price=Decimal("1000.00"), qty=2),
            CartLine(product_id="p2", product_name="Alfajor", unit_price=Decimal("250.00"), qty=3),
        ]
        totals = cart_totals(lines, None, Decimal(100))
        assert totals.final == Decimal(2800)

    def test_final_zero_round_step_step_of_one(self):
        lines = [
            CartLine(product_id="p1", product_name="Torta", unit_price=Decimal("1234.56"), qty=1),
        ]
        totals = cart_totals(lines, None, Decimal(1))
        assert totals.final == Decimal(1235)


# ─── Discount ─────────────────────────────────────────────────────────

class TestComputeDiscount:
    def test_no_coupon(self):
        assert compute_discount(Decimal(10000), None) == Decimal("0.00")

    def test_percent(self):
        discount = compute_discount(Decimal(10000), _coupon(value=Decimal(10)))
        assert discount == Decimal("1000.00")

    def test_percent_quantized_half_up(self):
        # 100.05 * 10% = 10.005 → 10.01
        discount = compute_discount(Decimal("100.05"), _coupon(value=Decimal(10)))
        assert discount == Decimal("10.01")

    def test_fixed(self):
        discount = compute_discount(
            Decimal(10000), _coupon(type="fixed", value=Decimal(500))
        )
        assert discount == Decimal("500.00")

    def test_fixed_capped_at_total(self):
        # fixed discount can never exceed the total
        discount = compute_discount(
            Decimal(500), _coupon(type="fixed", value=Decimal(1000))
        )
        assert discount == Decimal("500.00")

    def test_percent_100(self):
        discount = compute_discount(Decimal("321.99"), _coupon(value=Decimal(100)))
        assert discount == Decimal("321.99")

    def test_discount_computed_before_rounding(self):
        # discount on the raw subtotal (3750), then rounding on the net
        lines = [
            CartLine(product_id="p1", product_name="Torta", unit_price=Decimal("1000.00"), qty=2),
            CartLine(product_id="p2", product_name="Alfajor", unit_price=Decimal("250.00"), qty=3),
        ]
        totals = cart_totals(lines, _coupon(value=Decimal(10)), Decimal(100))
        assert totals.subtotal == Decimal("2750.00")
        assert totals.discount_amount == Decimal("275.00")
        assert totals.final == Decimal(2500)  # 2475 → step 100 HALF_UP


# ─── Coupon validation ────────────────────────────────────────────────

class TestValidateCouponForCart:
    NOW = datetime.datetime(2026, 10, 26, 12, 0, 0)

    def test_valid_coupon_passes(self):
        assert validate_coupon_for_cart(_coupon(), self.NOW) is None

    def test_paused_coupon(self):
        err = validate_coupon_for_cart(_coupon(status="paused"), self.NOW)
        assert err == "coupon_inactive"

    def test_before_valid_from(self):
        coupon = _coupon(
            valid_from=datetime.datetime(2026, 11, 1),
        )
        err = validate_coupon_for_cart(coupon, self.NOW)
        assert err == "coupon_inactive"

    def test_after_valid_until(self):
        coupon = _coupon(valid_until=datetime.datetime(2026, 10, 1))
        err = validate_coupon_for_cart(coupon, self.NOW)
        assert err == "coupon_expired"

    def test_window_ok(self):
        coupon = _coupon(
            valid_from=datetime.datetime(2026, 1, 1),
            valid_until=datetime.datetime(2026, 12, 31),
        )
        assert validate_coupon_for_cart(coupon, self.NOW) is None

    def test_max_uses_reached(self):
        coupon = _coupon(max_uses=5, uses=5)
        err = validate_coupon_for_cart(coupon, self.NOW)
        assert err == "coupon_limit_reached"

    def test_max_uses_not_reached(self):
        coupon = _coupon(max_uses=5, uses=4)
        assert validate_coupon_for_cart(coupon, self.NOW) is None

    def test_precedence_inactive_over_limit(self):
        coupon = _coupon(status="paused", max_uses=1, uses=1)
        assert validate_coupon_for_cart(coupon, self.NOW) == "coupon_inactive"

    @pytest.mark.parametrize("dt_naive,dt_aware", [
        (
            datetime.datetime(2026, 9, 1),
            datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC),
        ),
    ])
    def test_mixed_naive_aware_windows_are_normalized(self, dt_naive, dt_aware):
        # Coupon.__post_init__ normalizes to naive UTC; validation must not
        # crash comparing naive windows built from mixed inputs.
        coupon = _coupon(
            valid_from=dt_naive,
            valid_until=dt_aware,
        )
        err = validate_coupon_for_cart(coupon, self.NOW)
        # now=2026-10-26 is after valid_until (2026-10-01) → expired
        assert err == "coupon_expired"

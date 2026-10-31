"""Tests para el dominio de cupones (RF-P11-14, C3).

Cubre los invariantes del dataclass Coupon:
- code requerido, no-blank, <= MAX_COUPON_CODE
- type ∈ {percent, fixed}: percent → value 0–100; fixed → value ≥ 0
- valid_until > valid_from cuando ambas estan presentes
- max_uses positiva si presente; uses inicia 0 (no se incrementa en C3)
- status ∈ {active, paused} (default active)
"""
import datetime
from decimal import Decimal

import pytest
from domain.coupon import MAX_COUPON_CODE, Coupon


def _coupon(**overrides) -> Coupon:
    fields = {"code": "VERANO10", "type": "percent", "value": Decimal(20)}
    fields.update(overrides)
    return Coupon(**fields)


def test_valid_percent_coupon_defaults():
    """Un percent 20% valida con defaults: status active, uses 0."""
    coupon = _coupon()
    assert coupon.status == "active"
    assert coupon.uses == 0
    assert coupon.max_uses is None
    assert coupon.valid_from is None
    assert coupon.valid_until is None
    assert coupon.id  # uuid generado


def test_percent_bounds_inclusive():
    """percent: 0 y 100 son validos (extremos incluidos)."""
    assert _coupon(value=Decimal(0)).value == Decimal(0)
    assert _coupon(value=Decimal(100)).value == Decimal(100)


def test_percent_over_100_rejected():
    """percent > 100 → ValueError."""
    with pytest.raises(ValueError):
        _coupon(value=Decimal("100.01"))


def test_percent_negative_rejected():
    """percent < 0 → ValueError."""
    with pytest.raises(ValueError):
        _coupon(value=Decimal(-1))


def test_fixed_zero_ok():
    """fixed con value 0 es valido (Money ≥ 0)."""
    assert _coupon(type="fixed", value=Decimal(0)).type == "fixed"


def test_fixed_negative_rejected():
    """fixed con value negativo → ValueError."""
    with pytest.raises(ValueError):
        _coupon(type="fixed", value=Decimal("-0.01"))


def test_invalid_type_rejected():
    """type fuera de {percent, fixed} → ValueError."""
    with pytest.raises(ValueError):
        _coupon(type="second_item")  # type: ignore[arg-type]


def test_invalid_status_rejected():
    """status fuera de {active, paused} → ValueError."""
    with pytest.raises(ValueError):
        _coupon(status="expired")


def test_max_uses_positive_required():
    """max_uses debe ser positiva si esta presente."""
    assert _coupon(max_uses=1).max_uses == 1
    for bad in (0, -3):
        with pytest.raises(ValueError):
            _coupon(max_uses=bad)


def test_validity_window_consistent():
    """valid_until > valid_from → valido."""
    now = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    coupon = _coupon(
        valid_from=now, valid_until=now + datetime.timedelta(days=1)
    )
    assert coupon.valid_until > coupon.valid_from


def test_valid_until_before_from_rejected():
    """valid_until < valid_from → ValueError."""
    now = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    with pytest.raises(ValueError):
        _coupon(valid_from=now + datetime.timedelta(days=1), valid_until=now)


def test_valid_until_equal_from_rejected():
    """valid_until == valid_from → ValueError (debe ser estricto)."""
    now = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    with pytest.raises(ValueError):
        _coupon(valid_from=now, valid_until=now)


def test_single_bound_ok():
    """Una sola de valid_from/valid_until es valido."""
    now = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
    assert _coupon(valid_until=now).valid_from is None
    assert _coupon(valid_from=now).valid_until is None


def test_naive_datetimes_become_aware_utc():
    """naive → replace(tzinfo=UTC)."""
    naive = datetime.datetime(2026, 10, 1, 12, 0)
    coupon = _coupon(valid_from=naive, valid_until=naive + datetime.timedelta(days=1))
    assert coupon.valid_from == naive.replace(tzinfo=datetime.UTC)
    assert coupon.valid_from.utcoffset() == datetime.timedelta(0)
    assert coupon.valid_until.tzinfo is datetime.UTC


def test_aware_datetimes_converted_to_utc():
    """aware no-UTC → astimezone(UTC)."""
    tz = datetime.timezone(datetime.timedelta(hours=-3))
    coupon = _coupon(valid_from=datetime.datetime(2026, 10, 1, 9, 0, tzinfo=tz))
    assert coupon.valid_from == datetime.datetime(
        2026, 10, 1, 12, 0, tzinfo=datetime.UTC
    )
    assert coupon.valid_from.utcoffset() == datetime.timedelta(0)


def test_blank_code_rejected():
    """code solo espacios → ValueError."""
    with pytest.raises(ValueError):
        _coupon(code="   ")


def test_code_too_long_rejected():
    """code > MAX_COUPON_CODE → ValueError."""
    with pytest.raises(ValueError):
        _coupon(code="A" * (MAX_COUPON_CODE + 1))


def test_negative_uses_rejected():
    """uses negativo → ValueError."""
    with pytest.raises(ValueError):
        _coupon(uses=-1)

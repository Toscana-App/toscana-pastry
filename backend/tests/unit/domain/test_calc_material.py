import pytest
from decimal import Decimal

from domain.calc_material import (
    MAX_MATERIAL_INTERNAL_CODE,
    MAX_MATERIAL_NAME,
    MAX_MATERIAL_NOTES,
    MAX_MATERIAL_UNIT_OF_MEASURE,
    CalcMaterial,
    compute_unit_cost,
    derive_status,
)



class TestComputeUnitCost:
    def test_divides_price_by_quantity(self):
        assert compute_unit_cost(Decimal("100"), Decimal("2")) == Decimal("50.00")

    def test_rounds_half_up_to_cents(self):
        assert compute_unit_cost(Decimal("1"), Decimal("8")) == Decimal("0.13")

    def test_rounds_down_when_below_half(self):
        assert compute_unit_cost(Decimal("124"), Decimal("1000")) == Decimal("0.12")

    def test_third_decimal_truncates_to_two(self):
        assert compute_unit_cost(Decimal("10"), Decimal("3")) == Decimal("3.33")

    def test_missing_price_returns_none(self):
        assert compute_unit_cost(None, Decimal("2")) is None

    def test_missing_quantity_returns_none(self):
        assert compute_unit_cost(Decimal("5"), None) is None

    def test_missing_both_returns_none(self):
        assert compute_unit_cost(None, None) is None

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError):
            compute_unit_cost(Decimal("10"), Decimal("0"))

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            compute_unit_cost(Decimal("10"), Decimal("-1"))

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            compute_unit_cost(Decimal("-1"), Decimal("2"))



class TestDeriveStatus:
    def test_missing_price_is_incomplete(self):
        assert derive_status(None, Decimal("2")) == "incomplete"

    def test_missing_quantity_is_incomplete(self):
        assert derive_status(Decimal("5"), None) == "incomplete"

    def test_missing_both_is_incomplete(self):
        assert derive_status(None, None) == "incomplete"

    def test_both_present_is_active(self):
        assert derive_status(Decimal("5"), Decimal("2")) == "active"



def _material(**overrides):
    base = {"name": "Azucar Moreno"}
    base.update(overrides)
    return CalcMaterial(**base)


class TestCalcMaterialValidation:
    def test_valid_minimal(self):
        m = _material()
        assert m.name == "Azucar Moreno"
        assert m.unit_cost is None
        assert m.status == "incomplete"
        assert m.id

    def test_blank_name_raises(self):
        with pytest.raises(ValueError):
            _material(name="   ")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            _material(name="")

    def test_name_over_max_raises(self):
        with pytest.raises(ValueError):
            _material(name="x" * (MAX_MATERIAL_NAME + 1))

    def test_name_at_max_ok(self):
        assert _material(name="x" * MAX_MATERIAL_NAME).name == "x" * MAX_MATERIAL_NAME

    def test_internal_code_over_max_raises(self):
        with pytest.raises(ValueError):
            _material(internal_code="c" * (MAX_MATERIAL_INTERNAL_CODE + 1))

    def test_unit_of_measure_over_max_raises(self):
        with pytest.raises(ValueError):
            _material(unit_of_measure="u" * (MAX_MATERIAL_UNIT_OF_MEASURE + 1))

    def test_notes_over_max_raises(self):
        with pytest.raises(ValueError):
            _material(notes="n" * (MAX_MATERIAL_NOTES + 1))

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            _material(purchase_total_price=Decimal("-0.01"))

    def test_zero_package_quantity_raises(self):
        with pytest.raises(ValueError):
            _material(package_quantity=Decimal("0"))

    def test_negative_package_quantity_raises(self):
        with pytest.raises(ValueError):
            _material(package_quantity=Decimal("-1"))



class TestDerivedFields:
    def test_unit_cost_and_status_derived_when_complete(self):
        m = _material(
            purchase_total_price=Decimal("100"),
            package_quantity=Decimal("2"),
        )
        assert m.unit_cost == Decimal("50.00")
        assert m.status == "active"

    def test_incomplete_when_price_missing(self):
        m = _material(package_quantity=Decimal("2"))
        assert m.unit_cost is None
        assert m.status == "incomplete"

    def test_client_supplied_unit_cost_is_overridden(self):
        m = _material(
            purchase_total_price=Decimal("100"),
            package_quantity=Decimal("2"),
            unit_cost=Decimal("999.99"),
            status="inactive",
        )
        assert m.unit_cost == Decimal("50.00")
        assert m.status == "active"

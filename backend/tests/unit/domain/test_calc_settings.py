import pytest
from decimal import Decimal
from typing import Literal, cast

from domain.calc_settings import (
    CalcDefaultCost,
    CalcMaterialCategory,
    CalcProductCategory,
    CalcSettings,
    CalcSupplier,
    DEFAULT_BUSINESS_NAME,
    DEFAULT_CALC_SETTINGS,
    DEFAULT_DISCOUNT_PERCENT,
    DEFAULT_MAIN_CURRENCY_NAME,
    DEFAULT_MAIN_CURRENCY_SYMBOL,
    DEFAULT_MARGIN_PERCENT,
    DEFAULT_ROUNDING_MODE,
    DEFAULT_TAX_PERCENT,
    MAX_BUSINESS_NAME,
    MAX_CURRENCY_NAME,
    MAX_CURRENCY_SYMBOL,
)



class TestCalcSettingsDefaults:
    def test_default_business_name(self):
        assert DEFAULT_BUSINESS_NAME == "Mi Negocio"

    def test_default_currency_name(self):
        assert DEFAULT_MAIN_CURRENCY_NAME == "Peso"

    def test_default_currency_symbol(self):
        assert DEFAULT_MAIN_CURRENCY_SYMBOL == "$"

    def test_default_margin_percent(self):
        assert DEFAULT_MARGIN_PERCENT == Decimal("30")

    def test_default_discount_percent(self):
        assert DEFAULT_DISCOUNT_PERCENT == Decimal("0")

    def test_default_tax_percent(self):
        assert DEFAULT_TAX_PERCENT == Decimal("19")

    def test_default_rounding_mode(self):
        assert DEFAULT_ROUNDING_MODE == "none"

    def test_default_calc_settings_instance(self):
        s = DEFAULT_CALC_SETTINGS
        assert s.business_name == "Mi Negocio"
        assert s.main_currency_name == "Peso"
        assert s.main_currency_symbol == "$"
        assert s.default_margin_percent == Decimal("30")
        assert s.default_discount_percent == Decimal("0")
        assert s.default_tax_percent == Decimal("19")
        assert s.rounding_mode == "none"



class TestCalcSettingsRanges:
    def test_valid_defaults(self):
        CalcSettings()

    def test_margin_0_valid(self):
        CalcSettings(default_margin_percent=Decimal("0"))

    def test_margin_100_valid(self):
        CalcSettings(default_margin_percent=Decimal("100"))

    def test_margin_negative_rejected(self):
        with pytest.raises(ValueError, match="default_margin_percent"):
            CalcSettings(default_margin_percent=Decimal("-1"))

    def test_margin_over_100_rejected(self):
        with pytest.raises(ValueError, match="default_margin_percent"):
            CalcSettings(default_margin_percent=Decimal("101"))

    def test_discount_0_valid(self):
        CalcSettings(default_discount_percent=Decimal("0"))

    def test_discount_100_valid(self):
        CalcSettings(default_discount_percent=Decimal("100"))

    def test_discount_negative_rejected(self):
        with pytest.raises(ValueError, match="default_discount_percent"):
            CalcSettings(default_discount_percent=Decimal("-1"))

    def test_tax_0_valid(self):
        CalcSettings(default_tax_percent=Decimal("0"))

    def test_tax_100_valid(self):
        CalcSettings(default_tax_percent=Decimal("100"))

    def test_tax_negative_rejected(self):
        with pytest.raises(ValueError, match="default_tax_percent"):
            CalcSettings(default_tax_percent=Decimal("-1"))

    def test_rounding_mode_none(self):
        CalcSettings(rounding_mode="none")

    def test_rounding_mode_integer(self):
        CalcSettings(rounding_mode="integer")

    def test_rounding_mode_multiple_10(self):
        CalcSettings(rounding_mode="multiple_10")

    def test_rounding_mode_commercial_99(self):
        CalcSettings(rounding_mode="commercial_99")

    def test_rounding_mode_invalid_rejected(self):
        with pytest.raises(ValueError, match="rounding_mode invalido"):
            CalcSettings(rounding_mode="invalid")

    def test_business_name_min_length(self):
        CalcSettings(business_name="a")

    def test_business_name_max_length(self):
        CalcSettings(business_name="a" * MAX_BUSINESS_NAME)

    def test_business_name_too_short_rejected(self):
        with pytest.raises(ValueError, match="business_name longitud"):
            CalcSettings(business_name="")

    def test_business_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="business_name longitud"):
            CalcSettings(business_name="a" * (MAX_BUSINESS_NAME + 1))

    def test_currency_name_min_length(self):
        CalcSettings(main_currency_name="a")

    def test_currency_name_max_length(self):
        CalcSettings(main_currency_name="a" * MAX_CURRENCY_NAME)

    def test_currency_name_too_short_rejected(self):
        with pytest.raises(ValueError, match="main_currency_name longitud"):
            CalcSettings(main_currency_name="")

    def test_currency_symbol_min_length(self):
        CalcSettings(main_currency_symbol="$")

    def test_currency_symbol_max_length(self):
        CalcSettings(main_currency_symbol="a" * MAX_CURRENCY_SYMBOL)

    def test_currency_symbol_too_short_rejected(self):
        with pytest.raises(ValueError, match="main_currency_symbol longitud"):
            CalcSettings(main_currency_symbol="")

    def _make_settings_with_long_name(self, length: int) -> None:
        CalcSettings(business_name="a" * length)



class TestCalcMaterialCategory:
    def test_minimal_valid(self):
        CalcMaterialCategory(name="Harinas")

    def test_with_description(self):
        CalcMaterialCategory(name="Harinas", description="Todo tipo")

    def test_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="name longitud"):
            CalcMaterialCategory(name="a" * 81)

    def test_blank_name_rejected(self):
        with pytest.raises(ValueError, match="name requerido"):
            CalcMaterialCategory(name="   ")

    def test_description_max_length(self):
        CalcMaterialCategory(name="Cat", description="x" * 200)

    def test_description_too_long_rejected(self):
        with pytest.raises(ValueError, match="description max"):
            CalcMaterialCategory(name="Cat", description="x" * 201)



class TestCalcProductCategory:
    def test_minimal_valid(self):
        CalcProductCategory(name="Pasteles")

    def test_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="name longitud"):
            CalcProductCategory(name="a" * 81)

    def test_description_max_length(self):
        CalcProductCategory(name="Cat", description="x" * 200)

    def test_description_too_long_rejected(self):
        with pytest.raises(ValueError, match="description max"):
            CalcProductCategory(name="Cat", description="x" * 201)



class TestCalcSupplier:
    def test_minimal_valid(self):
        CalcSupplier(name="Proveedor A")

    def test_all_fields(self):
        CalcSupplier(
            name="Proveedor A",
            contact_name="Juan",
            phone="1234567890",
            email="juan@proveedor.com",
            notes="Notas de prueba",
        )

    def test_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="name longitud"):
            CalcSupplier(name="a" * 121)

    def test_contact_name_max(self):
        CalcSupplier(name="A", contact_name="x" * 120)

    def test_contact_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="contact_name max"):
            CalcSupplier(name="A", contact_name="x" * 121)

    def test_phone_max(self):
        CalcSupplier(name="A", phone="x" * 30)

    def test_phone_too_long_rejected(self):
        with pytest.raises(ValueError, match="phone max"):
            CalcSupplier(name="A", phone="x" * 31)

    def test_valid_email(self):
        CalcSupplier(name="A", email="test@example.com")

    def test_email_max_length(self):
        CalcSupplier(name="A", email="x" * 115 + "@a.co")

    def test_email_too_long_rejected(self):
        with pytest.raises(ValueError, match="email max"):
            CalcSupplier(name="A", email="x" * 121 + "@a.co")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValueError, match="email invalido"):
            CalcSupplier(name="A", email="not-an-email")

    def test_notes_max(self):
        CalcSupplier(name="A", notes="x" * 500)

    def test_notes_too_long_rejected(self):
        with pytest.raises(ValueError, match="notes max"):
            CalcSupplier(name="A", notes="x" * 501)



class TestCalcDefaultCost:
    def test_labor_active(self):
        CalcDefaultCost(
            name="Mano de obra",
            type="labor",
            default_unit_cost_or_rate=Decimal("5000"),
            default_quantity_or_minutes=Decimal("60"),
        )

    def test_extra_cost_active(self):
        CalcDefaultCost(
            name="Gas",
            type="extra_cost",
            default_unit_cost_or_rate=Decimal("1000"),
            default_quantity_or_minutes=Decimal("0"),
        )

    def test_inactive_status(self):
        CalcDefaultCost(
            name="Gas",
            type="extra_cost",
            default_unit_cost_or_rate=Decimal("1000"),
            default_quantity_or_minutes=Decimal("0"),
            status="inactive",
        )

    def test_zero_cost_valid(self):
        CalcDefaultCost(
            name="A",
            type="labor",
            default_unit_cost_or_rate=Decimal("0"),
            default_quantity_or_minutes=Decimal("0"),
        )

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError, match="default_unit_cost_or_rate"):
            CalcDefaultCost(
                name="A",
                type="labor",
                default_unit_cost_or_rate=Decimal("-1"),
                default_quantity_or_minutes=Decimal("0"),
            )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValueError, match="default_quantity_or_minutes"):
            CalcDefaultCost(
                name="A",
                type="labor",
                default_unit_cost_or_rate=Decimal("0"),
                default_quantity_or_minutes=Decimal("-1"),
            )

    def test_invalid_type_rejected(self):
        with pytest.raises(ValueError, match="type invalido"):
            CalcDefaultCost(
                name="A",
                type=cast(Literal["labor", "extra_cost"], "invalid"),
                default_unit_cost_or_rate=Decimal("0"),
                default_quantity_or_minutes=Decimal("0"),
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status invalido"):
            CalcDefaultCost(
                name="A",
                type="labor",
                default_unit_cost_or_rate=Decimal("0"),
                default_quantity_or_minutes=Decimal("0"),
                status=cast(Literal["active", "inactive"], "invalid"),
            )

    def test_name_max_length(self):
        CalcDefaultCost(
            name="a" * 120,
            type="labor",
            default_unit_cost_or_rate=Decimal("0"),
            default_quantity_or_minutes=Decimal("0"),
        )

    def test_name_too_long_rejected(self):
        with pytest.raises(ValueError, match="name longitud"):
            CalcDefaultCost(
                name="a" * 121,
                type="labor",
                default_unit_cost_or_rate=Decimal("0"),
                default_quantity_or_minutes=Decimal("0"),
            )

    def test_blank_name_rejected(self):
        with pytest.raises(ValueError, match="name requerido"):
            CalcDefaultCost(
                name="   ",
                type="labor",
                default_unit_cost_or_rate=Decimal("0"),
                default_quantity_or_minutes=Decimal("0"),
            )

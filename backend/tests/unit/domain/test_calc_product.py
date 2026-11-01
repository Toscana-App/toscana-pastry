"""Domain tests for the CalcProduct pricing engine (RF-P4CC-02..07).

Cubre las funciones puras del motor (Decimal + ROUND_HALF_UP, nunca
float), el caso de paridad obligatorio contra `pricing.js` legacy,
`apply_rounding` por modo, y la validacion de entidades frozen
(producto, lineas, versiones, costos).
"""
from decimal import Decimal

import pytest

from domain.calc_product import (
    MAX_PRODUCT_DESCRIPTION,
    MAX_PRODUCT_NAME,
    MAX_PRODUCT_NOTES,
    MAX_PRODUCT_SKU,
    CalcProduct,
    CalcProductCosts,
    CalcProductExtraCostLine,
    CalcProductLaborLine,
    CalcProductMaterialLine,
    CalcProductVersion,
    RecalculationResult,
    apply_rounding,
    calc_extra_line_cost,
    calc_labor_line_cost,
    calc_material_line_cost,
    calc_product_pricing,
    compute_costs,
    recalculate_product,
    resolve_material_line,
)
from domain.calc_material import CalcMaterial

D = Decimal


# ─── Line costs (RF-P4CC-02; paridad `|| 0` del JS) ────────────────────


class TestCalcMaterialLineCost:
    def test_parity_line_one(self):
        assert calc_material_line_cost(D("2.5"), D("456.80")) == D("1142.00")

    def test_parity_line_two(self):
        assert calc_material_line_cost(D("1"), D("78.90")) == D("78.90")

    def test_quantizes_to_cents_half_up(self):
        # 0.125 -> 0.13 (ROUND_HALF_UP; con banker's quedaria 0.12)
        assert calc_material_line_cost(D("0.125"), D("1")) == D("0.13")

    def test_missing_quantity_defaults_to_zero(self):
        assert calc_material_line_cost(None, D("10")) == D("0.00")

    def test_missing_unit_cost_defaults_to_zero(self):
        assert calc_material_line_cost(D("10"), None) == D("0.00")

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            calc_material_line_cost(D("-1"), D("10"))

    def test_negative_unit_cost_raises(self):
        with pytest.raises(ValueError):
            calc_material_line_cost(D("10"), D("-0.01"))


class TestCalcLaborLineCost:
    def test_parity(self):
        # 1500.00/h x 45 min = 1125.00
        assert calc_labor_line_cost(D("1500.00"), D("45")) == D("1125.00")

    def test_quantizes_to_cents_half_up(self):
        # 100 x 10/60 = 16.666... -> 16.67
        assert calc_labor_line_cost(D("100"), D("10")) == D("16.67")

    def test_missing_rate_defaults_to_zero(self):
        assert calc_labor_line_cost(None, D("45")) == D("0.00")

    def test_missing_minutes_defaults_to_zero(self):
        assert calc_labor_line_cost(D("1500"), None) == D("0.00")

    def test_negative_rate_raises(self):
        with pytest.raises(ValueError):
            calc_labor_line_cost(D("-1"), D("45"))

    def test_negative_minutes_raises(self):
        with pytest.raises(ValueError):
            calc_labor_line_cost(D("1500"), D("-45"))


class TestCalcExtraLineCost:
    def test_parity(self):
        assert calc_extra_line_cost(D("320.10"), D("3")) == D("960.30")

    def test_quantizes_to_cents_half_up(self):
        # 0.105 x 1 = 0.105 -> 0.11
        assert calc_extra_line_cost(D("0.105"), D("1")) == D("0.11")

    def test_missing_values_default_to_zero(self):
        assert calc_extra_line_cost(None, None) == D("0.00")

    def test_negative_unit_cost_raises(self):
        with pytest.raises(ValueError):
            calc_extra_line_cost(D("-0.01"), D("3"))

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            calc_extra_line_cost(D("320.10"), D("-3"))


# ─── calc_product_pricing (RF-P4CC-03; paridad con pricing.js) ─────────


class TestCalcProductPricingParity:
    """Caso de paridad obligatorio con `calcProductPricing` de pricing.js.

    Valores hardcodeados verificados contra el JS: cost_total = 3227.30
    (materiales 1142.00 + labor 1125.00 + extra 960.30), margin=30,
    discount=10, tax=19.
    """

    def test_parity_all_six_amounts(self):
        costs = calc_product_pricing(
            materials_cost_total=D("1142.00"),
            labor_cost_total=D("1125.00"),
            extra_cost_total=D("960.30"),
            margin_percent=D("30"),
            discount_percent=D("10"),
            tax_percent=D("19"),
        )
        assert costs.product_total_cost == D("3227.30")
        assert costs.profit_amount == D("1383.13")
        assert costs.discount_amount == D("-461.04")
        assert costs.adjusted_profit_amount == D("922.09")
        assert costs.tax_amount == D("788.38")
        assert costs.final_sale_price == D("4937.77")

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            ("none", D("4937.77")),
            ("integer", D("4938")),
            ("multiple_10", D("4940")),
            ("commercial_99", D("4999")),
        ],
    )
    def test_parity_final_per_rounding_mode(self, mode, expected):
        costs = calc_product_pricing(
            materials_cost_total=D("1142.00"),
            labor_cost_total=D("1125.00"),
            extra_cost_total=D("960.30"),
            margin_percent=D("30"),
            discount_percent=D("10"),
            tax_percent=D("19"),
        )
        assert apply_rounding(costs.final_sale_price, mode) == expected

    def test_multiple_material_lines_are_summed(self):
        # 2 lineas de material (1142.00 + 78.90) + labor + extra:
        # cost_total = 3306.20, cada monto cuantizado a centavos.
        costs = calc_product_pricing(
            materials_cost_total=D("1142.00") + D("78.90"),
            labor_cost_total=D("1125.00"),
            extra_cost_total=D("960.30"),
            margin_percent=D("30"),
            discount_percent=D("10"),
            tax_percent=D("19"),
        )
        assert costs.product_total_cost == D("3306.20")
        assert costs.profit_amount == D("1416.94")
        assert costs.discount_amount == D("-472.31")
        assert costs.adjusted_profit_amount == D("944.63")
        assert costs.tax_amount == D("807.66")
        assert costs.final_sale_price == D("5058.49")


class TestCalcProductPricingGuards:
    def test_margin_100_uses_guard_no_division_by_zero(self):
        # RF-P4CC-03: price_before_discount = cost_total, profit = 0.
        costs = calc_product_pricing(
            materials_cost_total=D("1000"),
            labor_cost_total=D("0"),
            extra_cost_total=D("0"),
            margin_percent=D("100"),
            discount_percent=D("10"),
            tax_percent=D("19"),
        )
        assert costs.product_total_cost == D("1000.00")
        assert costs.profit_amount == D("0.00")
        assert costs.discount_amount == D("-100.00")
        assert costs.adjusted_profit_amount == D("-100.00")
        # tax = (1000 + (-100)) * 0.19 = 171.00
        assert costs.tax_amount == D("171.00")
        assert costs.final_sale_price == D("1071.00")

    def test_margin_above_100_raises(self):
        # Percents fuera de [0, 100] -> ValueError (el guarda cubre
        # solo margin == 100, que es el borde permitido).
        with pytest.raises(ValueError):
            calc_product_pricing(
                materials_cost_total=D("1000"),
                labor_cost_total=D("0"),
                extra_cost_total=D("0"),
                margin_percent=D("120"),
                discount_percent=D("0"),
                tax_percent=D("0"),
            )

    def test_zero_margin_no_discount_final_is_cost_plus_tax(self):
        costs = calc_product_pricing(
            materials_cost_total=D("1000"),
            labor_cost_total=D("0"),
            extra_cost_total=D("0"),
            margin_percent=D("0"),
            discount_percent=D("0"),
            tax_percent=D("19"),
        )
        assert costs.final_sale_price == D("1190.00")

    def test_all_totals_zero_returns_zero_costs(self):
        costs = calc_product_pricing(
            materials_cost_total=D("0"),
            labor_cost_total=D("0"),
            extra_cost_total=D("0"),
            margin_percent=D("30"),
            discount_percent=D("10"),
            tax_percent=D("19"),
        )
        assert costs.product_total_cost == D("0.00")
        assert costs.final_sale_price == D("0.00")

    @pytest.mark.parametrize("percent", ["-0.01", "100.01", "1000"])
    def test_margin_percent_out_of_range_raises(self, percent):
        with pytest.raises(ValueError):
            calc_product_pricing(
                D("1"), D("0"), D("0"), D(percent), D("0"), D("0")
            )

    @pytest.mark.parametrize("percent", ["-1", "101"])
    def test_discount_percent_out_of_range_raises(self, percent):
        with pytest.raises(ValueError):
            calc_product_pricing(
                D("1"), D("0"), D("0"), D("0"), D(percent), D("0")
            )

    @pytest.mark.parametrize("percent", ["-1", "101"])
    def test_tax_percent_out_of_range_raises(self, percent):
        with pytest.raises(ValueError):
            calc_product_pricing(
                D("1"), D("0"), D("0"), D("0"), D("0"), D(percent)
            )

    def test_amounts_are_quantized_to_cents(self):
        # 1/3 x 10 = 3.3333... -> 3.33 en cada total de linea.
        costs = calc_product_pricing(
            materials_cost_total=D("10") / D("3"),
            labor_cost_total=D("0"),
            extra_cost_total=D("0"),
            margin_percent=D("0"),
            discount_percent=D("0"),
            tax_percent=D("0"),
        )
        assert costs.product_total_cost == D("3.33")
        assert costs.final_sale_price == D("3.33")


# ─── apply_rounding (RF-P4CC-04) ────────────────────────────────────────


class TestApplyRounding:
    def test_none_leaves_value_untouched(self):
        assert apply_rounding(D("4937.77"), "none") == D("4937.77")

    def test_integer_half_up(self):
        assert apply_rounding(D("4937.77"), "integer") == D("4938")

    def test_integer_tie_rounds_up(self):
        # 4938.50 -> 4939 (HALF_UP, no banker's)
        assert apply_rounding(D("4938.50"), "integer") == D("4939")

    def test_multiple_10(self):
        assert apply_rounding(D("4937.77"), "multiple_10") == D("4940")

    def test_multiple_10_half_up(self):
        assert apply_rounding(D("4935"), "multiple_10") == D("4940")

    def test_commercial_99(self):
        assert apply_rounding(D("4937.77"), "commercial_99") == D("4999")

    def test_commercial_99_exact_boundary(self):
        # 500 -> 499 (no salta al siguiente tramo)
        assert apply_rounding(D("500"), "commercial_99") == D("499")

    def test_commercial_99_one_above_boundary(self):
        # 500.01 -> 599
        assert apply_rounding(D("500.01"), "commercial_99") == D("599")

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            apply_rounding(D("10"), "wholesale")


# ─── compute_costs (RF-P4CC-05: solo el final se redondea) ─────────────


class TestComputeCosts:
    def test_rounding_applies_only_to_final_price(self):
        material_lines = [
            CalcProductMaterialLine(
                material_id="m1",
                material_name="Mantequilla",
                quantity_used=D("2.5"),
                unit_of_measure_snapshot="kg",
                unit_cost_snapshot=D("456.80"),
                line_total_cost=D("1142.00"),
                sort_order=0,
            )
        ]
        labor_lines = [
            CalcProductLaborLine(
                activity_name="Coccion",
                hourly_rate=D("1500.00"),
                minutes_required=D("45"),
                line_total_cost=D("1125.00"),
                sort_order=0,
            )
        ]
        extra_lines = [
            CalcProductExtraCostLine(
                concept_name="Embalaje",
                unit_cost=D("320.10"),
                quantity=D("3"),
                line_total_cost=D("960.30"),
                sort_order=0,
            )
        ]
        costs = compute_costs(
            material_lines,
            labor_lines,
            extra_lines,
            margin_percent=D("30"),
            discount_percent=D("10"),
            tax_percent=D("19"),
            rounding_mode="commercial_99",
        )
        # Los demas 5 montos no tocan el redondeo comercial.
        assert costs.product_total_cost == D("3227.30")
        assert costs.profit_amount == D("1383.13")
        assert costs.discount_amount == D("-461.04")
        assert costs.adjusted_profit_amount == D("922.09")
        assert costs.tax_amount == D("788.38")
        # Solo final_sale_price redondea.
        assert costs.final_sale_price == D("4999")

    def test_empty_lines_zero_costs(self):
        costs = compute_costs(
            [], [], [], D("30"), D("0"), D("19"), rounding_mode="none"
        )
        assert costs.final_sale_price == D("0.00")

    def test_unknown_rounding_mode_raises(self):
        with pytest.raises(ValueError):
            compute_costs(
                [], [], [], D("30"), D("0"), D("19"), rounding_mode="weird"
            )


# ─── CalcProduct validation (RF-P4CC-01) ───────────────────────────────


class TestCalcProduct:
    def test_defaults(self):
        product = CalcProduct(name="Brownie", margin_percent=D("30"))
        assert product.status == "draft"
        assert product.sku is None
        assert product.deleted_at is None
        assert product.last_recalculated_at is None
        assert product.id
        assert product.created_at and product.updated_at

    def test_strips_name(self):
        product = CalcProduct(name="  Brownie  ", margin_percent=D("30"))
        assert product.name == "Brownie"

    def test_blank_name_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(name="   ", margin_percent=D("30"))

    def test_name_too_long_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(
                name="x" * (MAX_PRODUCT_NAME + 1), margin_percent=D("30")
            )

    def test_blank_sku_becomes_none(self):
        product = CalcProduct(name="Brownie", sku="  ", margin_percent=D("30"))
        assert product.sku is None

    def test_strips_sku(self):
        product = CalcProduct(name="Brownie", sku=" BR-1 ", margin_percent=D("30"))
        assert product.sku == "BR-1"

    def test_sku_too_long_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(
                name="Brownie", sku="x" * (MAX_PRODUCT_SKU + 1), margin_percent=D("30")
            )

    def test_description_too_long_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(
                name="Brownie",
                margin_percent=D("30"),
                description="x" * (MAX_PRODUCT_DESCRIPTION + 1),
            )

    def test_notes_too_long_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(
                name="Brownie",
                margin_percent=D("30"),
                notes="x" * (MAX_PRODUCT_NOTES + 1),
            )

    @pytest.mark.parametrize(
        "percent", ["-0.01", "100.01", "-1", "101"]
    )
    def test_percents_out_of_range_raise(self, percent):
        with pytest.raises(ValueError):
            CalcProduct(name="Brownie", margin_percent=D(percent))
        with pytest.raises(ValueError):
            CalcProduct(
                name="Brownie", margin_percent=D("0"), discount_percent=D(percent)
            )
        with pytest.raises(ValueError):
            CalcProduct(
                name="Brownie", margin_percent=D("0"), tax_percent=D(percent)
            )

    def test_percents_at_bounds_are_valid(self):
        product = CalcProduct(
            name="Brownie",
            margin_percent=D("100"),
            discount_percent=D("0"),
            tax_percent=D("100"),
        )
        assert product.margin_percent == D("100")

    @pytest.mark.parametrize("status", ["draft", "active", "archived"])
    def test_allowed_statuses(self, status):
        assert (
            CalcProduct(name="Brownie", margin_percent=D("30"), status=status).status
            == status
        )

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            CalcProduct(name="Brownie", margin_percent=D("30"), status="bogus")


# ─── Line validation ────────────────────────────────────────────────────


class TestLineValidation:
    def test_labor_line_blank_name_raises(self):
        with pytest.raises(ValueError):
            CalcProductLaborLine(
                activity_name="   ",
                hourly_rate=D("10"),
                minutes_required=D("5"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_labor_line_negative_rate_raises(self):
        with pytest.raises(ValueError):
            CalcProductLaborLine(
                activity_name="Coccion",
                hourly_rate=D("-1"),
                minutes_required=D("5"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_labor_line_negative_minutes_raises(self):
        with pytest.raises(ValueError):
            CalcProductLaborLine(
                activity_name="Coccion",
                hourly_rate=D("10"),
                minutes_required=D("-5"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_extra_line_blank_concept_raises(self):
        with pytest.raises(ValueError):
            CalcProductExtraCostLine(
                concept_name="",
                unit_cost=D("1"),
                quantity=D("1"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_extra_line_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            CalcProductExtraCostLine(
                concept_name="Embalaje",
                unit_cost=D("1"),
                quantity=D("-1"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_material_line_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            CalcProductMaterialLine(
                material_id="m1",
                material_name="Mantequilla",
                quantity_used=D("-2.5"),
                unit_of_measure_snapshot="kg",
                unit_cost_snapshot=D("10"),
                line_total_cost=D("0"),
                sort_order=0,
            )

    def test_material_line_negative_snapshot_cost_raises(self):
        with pytest.raises(ValueError):
            CalcProductMaterialLine(
                material_id="m1",
                material_name="Mantequilla",
                quantity_used=D("2"),
                unit_of_measure_snapshot="kg",
                unit_cost_snapshot=D("-0.01"),
                line_total_cost=D("0"),
                sort_order=0,
            )


# ─── CalcProductVersion ─────────────────────────────────────────────────


class TestCalcProductVersion:
    def test_fields_and_defaults(self):
        version = CalcProductVersion(
            product_id="p1",
            version_number=1,
            product_total_cost=D("3227.30"),
            profit_amount=D("1383.13"),
            discount_amount=D("-461.04"),
            adjusted_profit_amount=D("922.09"),
            tax_amount=D("788.38"),
            final_sale_price=D("4937.77"),
        )
        assert version.id
        assert version.changed_at

    def test_version_number_below_one_raises(self):
        with pytest.raises(ValueError):
            CalcProductVersion(
                product_id="p1",
                version_number=0,
                product_total_cost=D("0"),
                profit_amount=D("0"),
                discount_amount=D("0"),
                adjusted_profit_amount=D("0"),
                tax_amount=D("0"),
                final_sale_price=D("0"),
            )


# ─── CalcProductCosts ───────────────────────────────────────────────────


class TestCalcProductCosts:
    def test_field_order_matches_js(self):
        costs = CalcProductCosts(
            product_total_cost=D("1"),
            profit_amount=D("2"),
            discount_amount=D("3"),
            adjusted_profit_amount=D("4"),
            tax_amount=D("5"),
            final_sale_price=D("6"),
        )
        assert (
            costs.product_total_cost,
            costs.profit_amount,
            costs.discount_amount,
            costs.adjusted_profit_amount,
            costs.tax_amount,
            costs.final_sale_price,
        ) == (D("1"), D("2"), D("3"), D("4"), D("5"), D("6"))


# ─── resolve_material_line / recalculate_product (reglas 5/6, D4) ──────


def _material(unit_cost, material_id="m1", name="Harina"):
    # unit_cost se deriva en el dominio: precio / cantidad (None -> incomplete).
    return CalcMaterial(
        id=material_id,
        name=name,
        unit_of_measure="kg",
        purchase_total_price=unit_cost,
        package_quantity=D("1") if unit_cost is not None else None,
    )


def _stale_material_line(material_id="m1", quantity="2"):
    return CalcProductMaterialLine(
        material_id=material_id,
        material_name="Viejo",
        quantity_used=D(quantity),
        unit_of_measure_snapshot="g",
        unit_cost_snapshot=D("1.00"),
        line_total_cost=D("2.00"),
        sort_order=3,
    )


class TestResolveMaterialLine:
    def test_snapshot_comes_from_material(self):
        line = resolve_material_line(_material(D("5.00")), D("3"), 1)
        assert line.material_name == "Harina"
        assert line.unit_of_measure_snapshot == "kg"
        assert line.unit_cost_snapshot == D("5.00")
        assert line.line_total_cost == D("15.00")
        assert line.sort_order == 1

    def test_incomplete_material_resolves_to_zero(self):
        line = resolve_material_line(_material(None), D("3"), 0)
        assert line.unit_cost_snapshot == D("0.00")
        assert line.line_total_cost == D("0.00")

    def test_keeps_given_line_id(self):
        line = resolve_material_line(_material(D("1")), D("1"), 0, line_id="abc")
        assert line.id == "abc"


class TestRecalculateProduct:
    def _product(self):
        return CalcProduct(name="Torta", margin_percent=D("0"))

    def test_re_resolves_snapshot_and_flags_new_version(self):
        old = _stale_material_line()
        result = recalculate_product(
            self._product(),
            [old],
            [],
            [],
            {"m1": _material(D("10.00"))},
            "none",
        )
        assert isinstance(result, RecalculationResult)
        (line,) = result.material_lines
        assert line.id == old.id
        assert line.sort_order == 3
        assert line.material_name == "Harina"
        assert line.unit_cost_snapshot == D("10.00")
        assert line.line_total_cost == D("20.00")
        assert result.old_costs.final_sale_price == D("2.00")
        assert result.new_costs.final_sale_price == D("20.00")
        assert result.creates_version is True

    def test_no_price_change_creates_no_version(self):
        result = recalculate_product(
            self._product(),
            [_stale_material_line()],
            [],
            [],
            {"m1": _material(D("1.00"))},
            "none",
        )
        assert result.creates_version is False

    def test_missing_material_keeps_line_unchanged(self):
        old = _stale_material_line()
        result = recalculate_product(self._product(), [old], [], [], {}, "none")
        assert result.material_lines == [old]
        assert result.creates_version is False

    def test_recomputes_labor_and_extra_totals(self):
        labor = CalcProductLaborLine(
            activity_name="Horno",
            hourly_rate=D("60"),
            minutes_required=D("30"),
            line_total_cost=D("0.00"),
            sort_order=0,
        )
        extra = CalcProductExtraCostLine(
            concept_name="Caja",
            unit_cost=D("2.50"),
            quantity=D("2"),
            line_total_cost=D("0.00"),
            sort_order=0,
        )
        result = recalculate_product(
            self._product(), [], [labor], [extra], {}, "none"
        )
        assert result.labor_lines[0].line_total_cost == D("30.00")
        assert result.extra_lines[0].line_total_cost == D("5.00")
        assert result.new_costs.final_sale_price == D("35.00")
        assert result.creates_version is True

    def test_unknown_rounding_mode_raises(self):
        with pytest.raises(ValueError):
            recalculate_product(self._product(), [], [], [], {}, "bogus")

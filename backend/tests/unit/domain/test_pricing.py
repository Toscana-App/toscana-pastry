from decimal import Decimal

import pytest

from domain.pricing import (
    CostBreakdown,
    PricingSettings,
    UnitConversionError,
    calculate_price,
    cost_of_quantity,
    round_to_step,
    to_base_units,
)


def make_settings(**overrides) -> PricingSettings:
    base = dict(
        hourly_rate=Decimal("150"),
        margin_pct=Decimal("100"),
        round_step=Decimal("5"),
    )
    base.update(overrides)
    return PricingSettings(**base)


class TestToBaseUnits:
    def test_kg_a_gramos(self):
        assert to_base_units(Decimal("2.5"), "kg") == Decimal("2500")

    def test_litros_a_milis(self):
        assert to_base_units(Decimal("0.5"), "l") == Decimal("500")

    def test_base_no_se_convierte(self):
        assert to_base_units(Decimal("3"), "g") == Decimal("3")

    def test_unidad_desconocida_lanza(self):
        with pytest.raises(UnitConversionError):
            to_base_units(Decimal("1"), "onzas")


class TestCostOfQuantity:
    def test_gramos_con_precio_por_kilo(self):
        # 250g de harina a $2.800/kg = $700 (caso de la spec)
        assert cost_of_quantity(Decimal("250"), "g", Decimal("2800"), "kg") == Decimal("700.00")

    def test_unidades_iguales(self):
        # 4 huevos a $90/unidad = $360
        assert cost_of_quantity(Decimal("4"), "unidad", Decimal("90"), "unidad") == Decimal("360.00")

    def test_litros_directo(self):
        # 1.5L de crema a $1.200/L = $1.800
        assert cost_of_quantity(Decimal("1.5"), "l", Decimal("1200"), "l") == Decimal("1800.00")

    def test_mililitros_con_precio_por_litro(self):
        assert cost_of_quantity(Decimal("200"), "ml", Decimal("1200"), "l") == Decimal("240.00")

    def test_cantidad_negativa_lanza(self):
        with pytest.raises(ValueError):
            cost_of_quantity(Decimal("-1"), "g", Decimal("10"), "kg")

    def test_precio_negativo_lanza(self):
        with pytest.raises(ValueError):
            cost_of_quantity(Decimal("1"), "g", Decimal("-10"), "kg")

    def test_unidades_incompatibles_lanza(self):
        with pytest.raises(UnitConversionError):
            cost_of_quantity(Decimal("100"), "g", Decimal("90"), "unidad")

    def test_precio_cero_da_cero(self):
        assert cost_of_quantity(Decimal("100"), "g", Decimal("0"), "kg") == Decimal("0.00")


class TestRoundToStep:
    def test_redondea_al_paso_cincuenta(self):
        assert round_to_step(Decimal("3287.50"), Decimal("5")) == Decimal("3290")

    def test_baja_cuando_no_alcanza_la_mitad(self):
        # HALF_UP, no "redondear siempre hacia arriba": 3287.20/5=657.44 -> 657
        assert round_to_step(Decimal("3287.20"), Decimal("5")) == Decimal("3285")

    def test_paso_diez(self):
        assert round_to_step(Decimal("123.4"), Decimal("10")) == Decimal("120")

    def test_paso_invalido_lanza(self):
        with pytest.raises(ValueError):
            round_to_step(Decimal("10"), Decimal("0"))


class TestPricingSettings:
    def test_margen_superior_a_200_lanza(self):
        with pytest.raises(ValueError):
            make_settings(margin_pct=Decimal("200.01"))

    def test_margen_negativo_lanza(self):
        with pytest.raises(ValueError):
            make_settings(margin_pct=Decimal("-1"))

    def test_paso_cero_lanza(self):
        with pytest.raises(ValueError):
            make_settings(round_step=Decimal("0"))

    def test_valor_hora_negativo_lanza(self):
        with pytest.raises(ValueError):
            make_settings(hourly_rate=Decimal("-1"))

    def test_porcentajes_negativos_lanzan(self):
        with pytest.raises(ValueError):
            make_settings(include_gas=True, gas_pct=Decimal("-10"))
        with pytest.raises(ValueError):
            make_settings(include_waste=True, waste_pct=Decimal("-10"))


class TestCalculatePrice:
    ITEMS_TORTA = [
        (Decimal("250"), "g", Decimal("2800"), "kg"),
        (Decimal("4"), "unidad", Decimal("90"), "unidad"),
        (Decimal("1.5"), "l", Decimal("1200"), "l"),
    ]

    def test_caso_completo_del_plan(self):
        # 700 (harina) + 360 (huevos) + 1800 (crema) = 2860; + mano de obra 75 = 2935
        # margen 150% -> 2935 x 2.5 = 7337.50; paso 5 -> 7340
        b = calculate_price(
            self.ITEMS_TORTA,
            30,
            make_settings(margin_pct=Decimal("150")),
        )
        assert isinstance(b, CostBreakdown)
        assert b.materials == Decimal("2860.00")
        assert b.labor == Decimal("75.00")
        assert b.base == Decimal("2935.00")
        assert b.final == Decimal("7337.50")
        assert b.rounded == Decimal("7340.00")

    def test_gas_se_aplica_sobre_materiales(self):
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 0, make_settings(include_gas=True, gas_pct=Decimal("10")))
        assert b.materials == Decimal("1000.00")
        assert b.gas == Decimal("100.00")
        assert b.base == Decimal("1100.00")

    def test_gas_desactivado_nunca_agrega(self):
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 0, make_settings(gas_pct=Decimal("50")))
        assert b.gas == Decimal("0")

    def test_merma_aumenta_materiales(self):
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 0, make_settings(include_waste=True, waste_pct=Decimal("5")))
        assert b.materials == Decimal("1000.00")
        assert b.waste == Decimal("50.00")
        assert b.materials_con_merma == Decimal("1050.00")
        assert b.base == Decimal("1050.00")

    def test_manos_obra_desactivada(self):
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 60, make_settings(include_labor=False))
        assert b.labor == Decimal("0.00")
        assert b.base == Decimal("1000.00")

    def test_manos_obra_por_minutos(self):
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 90, make_settings(hourly_rate=Decimal("200")))
        assert b.labor == Decimal("300.00")

    def test_redondeo_half_up_baja_por_debajo_de_la_mitad(self):
        # 1000 x 1.2874 = 1287.40; paso 1 -> 1287 (no 1288)
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 0, make_settings(margin_pct=Decimal("28.74"), round_step=Decimal("1")))
        assert b.final == Decimal("1287.40")
        assert b.rounded == Decimal("1287")

    def test_redondeo_half_up_sube_en_la_mitad(self):
        # 1000 x 1.3005 = 1300.50; paso 1 -> 1301
        items = [(Decimal("1"), "kg", Decimal("1000"), "kg")]
        b = calculate_price(items, 0, make_settings(margin_pct=Decimal("30.05"), round_step=Decimal("1")))
        assert b.final == Decimal("1300.50")
        assert b.rounded == Decimal("1301")

    def test_item_vacio_da_cero(self):
        b = calculate_price([], 0, make_settings())
        assert b.materials == Decimal("0.00")
        assert b.base == Decimal("0.00")
        assert b.final == Decimal("0.00")
        assert b.rounded == Decimal("0")

    def test_minutos_negativos_lanzan(self):
        with pytest.raises(ValueError):
            calculate_price(self.ITEMS_TORTA, -1, make_settings())

    def test_item_con_unidades_incompatibles_lanza(self):
        items = [(Decimal("100"), "g", Decimal("90"), "unidad")]
        with pytest.raises(UnitConversionError):
            calculate_price(items, 0, make_settings())

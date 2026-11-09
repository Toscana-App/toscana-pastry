import datetime
from decimal import Decimal

import pytest

from domain.models import BusinessSettings, Ingredient, Product, RecipeItem
from domain.order_pricing import (
    check_stock,
    plan_order_deductions,
    price_order_item,
)
from domain.orders import (
    Customer,
    InvalidStatusTransitionError,
    Order,
    OrderItem,
    transition_status,
)
from domain.pricing import UnitConversionError


def make_tenant_settings(**overrides) -> BusinessSettings:
    base = dict(
        hourly_rate=Decimal("150"),
        margin_pct=Decimal("100"),
        round_step=Decimal("5"),
    )
    base.update(overrides)
    return BusinessSettings(**base)


def make_flour(
    price="2800", stock="10", deleted_at=None
) -> Ingredient:
    return Ingredient(
        name="Harina",
        unit="kg",
        price_per_unit=Decimal(price),
        stock_qty=Decimal(stock),
        id="flour",
        deleted_at=deleted_at,
    )


def make_torta(flour_id: str = "flour") -> Product:
    return Product(
        name="Torta de Limón",
        category="Tortas",
        recipe=(RecipeItem(ingredient_id=flour_id, qty=Decimal("250"), unit="g"),),
        prep_time_min=30,
        servings=6,
        id="torta",
    )




class TestTransitions:
    def test_flujo_hasta_entregar(self):
        assert transition_status("nuevo", "confirmado") == "confirmado"
        assert transition_status("confirmado", "entregado") == "entregado"

    def test_cancelar_solo_desde_confirmado(self):
        assert transition_status("confirmado", "cancelado") == "cancelado"
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("nuevo", "cancelado")
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("entregado", "cancelado")

    def test_estados_finales_no_avanzan(self):
        for target in ("nuevo", "confirmado", "entregado", "cancelado"):
            with pytest.raises(InvalidStatusTransitionError):
                transition_status("entregado", target)
            with pytest.raises(InvalidStatusTransitionError):
                transition_status("cancelado", target)

    def test_atajos_invalidos(self):
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("nuevo", "entregado")
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("nuevo", "nuevo")
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("entregado", "confirmado")

    def test_estado_desconocido_lanza(self):
        with pytest.raises(InvalidStatusTransitionError):
            transition_status("perdido", "nuevo")




class TestCustomer:
    def test_normaliza_nombre_y_telefono(self):
        customer = Customer(name="  María  ", phone="+54 357 555-1234")
        assert customer.name == "María"
        assert customer.phone == "543575551234"

    def test_dedupe_ignora_acentos_case_y_espacios(self):
        a = Customer(name="  María ", phone="357-5551234")
        b = Customer(name="maria", phone="+357 555 1234")
        assert a.name_norm == b.name_norm
        assert a.phone_norm == b.phone_norm

    def test_dedupe_no_confunde_clientes_distintos(self):
        a = Customer(name="María", phone="3575551234")
        b = Customer(name="María", phone="3575551235")
        c = Customer(name="Jose", phone="3575551234")
        assert a.phone_norm != b.phone_norm
        assert a.name_norm != c.name_norm

    def test_telefono_sin_digitos_lanza(self):
        with pytest.raises(ValueError):
            Customer(name="María", phone="hola")

    def test_telefono_corto_lanza(self):
        with pytest.raises(ValueError):
            Customer(name="María", phone="1234")

    def test_nombre_corto_lanza(self):
        with pytest.raises(ValueError):
            Customer(name="M", phone="3575551234")




class TestPortionScaling:
    def test_porciones_iguales_no_escalas(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=1,
            portions=6,
        )
        assert snap.lines[0].qty == Decimal("250")
        assert snap.materials == Decimal("700.00")
        assert snap.labor == Decimal("75.00")

    def test_dobles_porciones_dobla_insumos_y_mano_de_obra(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=1,
            portions=12,
        )
        assert snap.lines[0].qty == Decimal("500")
        assert snap.materials == Decimal("1400.00")
        assert snap.labor == Decimal("150.00")
        assert snap.base == Decimal("1550.00")
        assert snap.rounded == Decimal("3100.00")

    def test_qty_multiplica_tambien(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=2,
            portions=12,
        )
        assert snap.lines[0].qty == Decimal("1000")
        assert snap.materials == Decimal("2800.00")
        assert snap.rounded == Decimal("6200.00")

    def test_porciones_fraccionales_escalas_proporcional(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=1,
            portions=9,
        )
        assert snap.lines[0].qty == Decimal("375")
        assert snap.materials == Decimal("1050.00")




class TestMarginOverride:
    def test_override_reemplaza_el_del_tenant(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=1,
            portions=6,
            margin_override=Decimal("200"),
        )
        assert snap.margin_pct == Decimal("200")
        assert snap.rounded == Decimal("2325.00")

    def test_override_cero_vende_a_costo_redondeado(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=1,
            portions=6,
            margin_override=Decimal("0"),
        )
        assert snap.rounded == Decimal("775.00")

    def test_override_fuera_de_rango_lanza(self):
        with pytest.raises(ValueError):
            price_order_item(
                make_torta(),
                {"flour": make_flour()},
                make_tenant_settings(),
                qty=1,
                portions=6,
                margin_override=Decimal("201"),
            )
        with pytest.raises(ValueError):
            price_order_item(
                make_torta(),
                {"flour": make_flour()},
                make_tenant_settings(),
                qty=1,
                portions=6,
                margin_override=Decimal("-1"),
            )




class TestIncompleteProduct:
    def test_insumo_borrado_entra_con_costo_cero(self):
        snap = price_order_item(
            make_torta(),
            {},
            make_tenant_settings(),
            qty=1,
            portions=6,
        )
        assert snap.complete is False
        assert len(snap.missing) == 1
        assert "flour" in snap.missing[0]
        line = snap.lines[0]
        assert line.is_missing is True
        assert line.cost == Decimal("0")
        assert snap.rounded == Decimal("150.00")

    def test_insumo_con_precio_cero_es_missing(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour(price="0")},
            make_tenant_settings(),
            qty=1,
            portions=6,
        )
        assert snap.complete is False
        assert snap.lines[0].is_missing is True

    def test_snapshot_parcial_no_desuenta_stock(self):
        snap = price_order_item(
            make_torta(),
            {},
            make_tenant_settings(),
            qty=1,
            portions=6,
        )
        deductions = plan_order_deductions({snap.lines[0].ingredient_id: snap})
        assert deductions == {}

    def test_deduction_suma_lineas_por_insumo(self):
        snap = price_order_item(
            make_torta(),
            {"flour": make_flour()},
            make_tenant_settings(),
            qty=2,
            portions=12,
        )
        deductions = plan_order_deductions({"x": snap})
        assert deductions == {"flour": Decimal("1000")}

    def test_unidades_incompatibles_lanza(self):
        product = Product(
            name="Torta Rara",
            category="Tortas",
            recipe=(RecipeItem(ingredient_id="flour", qty=Decimal("2"), unit="unidad"),),
            prep_time_min=10,
            servings=4,
        )
        with pytest.raises(UnitConversionError):
            price_order_item(
                product,
                {"flour": make_flour()},
                make_tenant_settings(),
                qty=1,
                portions=4,
            )




class TestCheckStock:
    def test_sin_corto_da_vacio(self):
        assert (
            check_stock({"flour": Decimal("1")}, {"flour": Decimal("5")}) == {}
        )

    def test_corto_devuelve_cuanto_falta(self):
        shortage = check_stock(
            {"flour": Decimal("10"), "sugar": Decimal("1")},
            {"flour": Decimal("3"), "sugar": Decimal("100")},
        )
        assert shortage == {"flour": Decimal("7")}

    def test_insumo_sin_stock_da_corto_total(self):
        shortage = check_stock({"flour": Decimal("2")}, {})
        assert shortage == {"flour": Decimal("2")}




class TestOrderTotal:
    def test_total_suma_los_redondeados(self):
        from domain.orders import OrderItemSnapshot

        item_a = OrderItem(
            product_id="a", qty=1, portions=6, product_name="A", id="ia"
        )
        item_b = OrderItem(
            product_id="b", qty=2, portions=6, product_name="B", id="ib"
        )
        order = Order(
            customer_id="c",
            customer_name="María",
            customer_phone="3575551234",
            date=datetime.date(2026, 10, 20),
            items=(item_a, item_b),
            snapshots={
                "ia": OrderItemSnapshot(rounded=Decimal("1550.00")),
                "ib": OrderItemSnapshot(rounded=Decimal("775.00")),
            },
        )
        assert order.total == Decimal("2325.00")

    def test_estado_invalido_lanza(self):
        with pytest.raises(ValueError):
            Order(
                customer_id="c",
                customer_name="María",
                customer_phone="3575551234",
                date=datetime.date(2026, 10, 20),
                status="vuelto",
            )

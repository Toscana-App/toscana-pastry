from domain.imports import check_columns

from api.v1.imports.adapters import ADAPTERS, ENTITIES
from api.v1.imports.adapters.customers_adapter import CustomersAdapter
from api.v1.imports.adapters.products_adapter import ProductsAdapter
from api.v1.imports.parsers import detect_delimiter, parse_csv, rows_to_dicts


def _roundtrip_passes(adapter) -> bool:
    text = adapter.template()
    delimiter = detect_delimiter(text)
    headers, rows = parse_csv(text, delimiter)
    assert headers == adapter.columns
    dicts = rows_to_dicts(headers, rows)
    assert len(dicts) >= 2
    return all(adapter.validate_row(d)[1] == [] for d in dicts)


class TestRoundTripTodas:

    def test_entidades_registradas(self):
        assert set(ENTITIES) == {"ingredients", "products", "customers"}
        assert set(ADAPTERS) == set(ENTITIES)

    def test_plantilla_de_cada_entidad_pasa(self):
        for entity in ENTITIES:
            adapter = ADAPTERS[entity]
            assert _roundtrip_passes(adapter), f"falla round-trip para {entity}"


class TestProducts:
    def _adapter(self):
        return ProductsAdapter()

    def test_fila_valida(self):
        data, errors = self._adapter().validate_row(
            {
                "nombre": "Torta de limón",
                "categoria": "Tortas",
                "unidad": "unidad",
                "costo_unitario": "3.000",
                "precio_venta": "6000",
                "stock_inicial": "10",
            }
        )
        assert errors == []
        assert data["name"] == "Torta de limón"
        assert data["category"] == "Tortas"

    def test_falta_nombre(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "", "categoria": "Tortas"}
        )
        assert any("nombre" in e.lower() for e in errors)

    def test_nombre_corto(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "A", "categoria": "Tortas"}
        )
        assert any("nombre" in e.lower() for e in errors)

    def test_falta_categoria(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "Torta", "categoria": ""}
        )
        assert any("categoría" in e.lower() or "categoria" in e.lower() for e in errors)

    def test_precio_no_numerico(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "Torta", "categoria": "Tortas", "precio_venta": "abc"}
        )
        assert any("precio venta" in e.lower() for e in errors)

    def test_stock_negativo(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "Torta", "categoria": "Tortas", "stock_inicial": "-1"}
        )
        assert any("stock inicial" in e.lower() for e in errors)

    def test_columnas_plan(self):
        assert self._adapter().columns == [
            "nombre",
            "categoria",
            "unidad",
            "costo_unitario",
            "precio_venta",
            "stock_inicial",
        ]

    def test_v1_no_inserta_en_confirm(self):
        assert self._adapter().inserts_on_confirm is False
        assert self._adapter().confirm_message


class TestCustomers:
    def _adapter(self):
        return CustomersAdapter()

    def test_fila_valida(self):
        data, errors = self._adapter().validate_row(
            {"nombre": "María González", "telefono": "11 5555-0101"}
        )
        assert errors == []
        assert data["name"] == "María González"
        assert data["phone"] == "1155550101"
        assert data["name_norm"]

    def test_falta_telefono(self):
        _, errors = self._adapter().validate_row({"nombre": "María", "telefono": ""})
        assert any("teléfono" in e.lower() or "telefono" in e.lower() for e in errors)

    def test_telefono_sin_digitos(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "María", "telefono": "hola"}
        )
        assert any("teléfono" in e.lower() or "telefono" in e.lower() for e in errors)

    def test_telefono_muy_corto(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "María", "telefono": "123"}
        )
        assert any("teléfono" in e.lower() or "telefono" in e.lower() for e in errors)

    def test_nombre_muy_corto(self):
        _, errors = self._adapter().validate_row(
            {"nombre": "A", "telefono": "1155550101"}
        )
        assert any("nombre" in e.lower() for e in errors)

    def test_columnas(self):
        assert self._adapter().columns == ["nombre", "telefono"]

    def test_check_columns_cliente(self):
        adapter = self._adapter()
        check_columns(adapter.columns, ["telefono", "nombre"])

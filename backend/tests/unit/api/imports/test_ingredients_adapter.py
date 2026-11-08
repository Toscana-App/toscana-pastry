from domain.imports import ColumnMismatchError, check_columns

from api.v1.imports.adapters.ingredients_adapter import IngredientsAdapter
from api.v1.imports.parsers import detect_delimiter, parse_csv, rows_to_dicts


def _adapter() -> IngredientsAdapter:
    return IngredientsAdapter()


class TestValidacion:
    def test_fila_valida(self):
        data, errors = _adapter().validate_row(
            {"nombre": "Harina 000", "cantidad": "1", "unidad": "kg", "precio": "1200"}
        )
        assert errors == []
        assert data["name"] == "Harina 000"
        assert data["unit"] == "kg"
        assert data["price_per_unit_cents"] == 120000
        assert data["stock_qty"] == "1"

    def test_precio_con_coma_decimal(self):
        data, errors = _adapter().validate_row(
            {"nombre": "A", "cantidad": "", "unidad": "kg", "precio": "1.200,5"}
        )
        assert errors == []
        assert data["price_per_unit_cents"] == 120050

    def test_precio_con_punto_miles(self):
        data, _ = _adapter().validate_row(
            {"nombre": "A", "cantidad": "", "unidad": "kg", "precio": "2.800"}
        )
        assert data["price_per_unit_cents"] == 280000

    def test_cantidad_decimal_con_coma(self):
        data, errors = _adapter().validate_row(
            {"nombre": "A", "cantidad": "1,5", "unidad": "kg", "precio": "10"}
        )
        assert errors == []
        assert data["stock_qty"] == "1.5"

    def test_cantidad_vacia_por_defecto_cero(self):
        data, errors = _adapter().validate_row(
            {"nombre": "A", "cantidad": "", "unidad": "kg", "precio": "10"}
        )
        assert errors == []
        assert data["stock_qty"] == "0"

    def test_unidad_vacia_por_defecto(self):
        data, errors = _adapter().validate_row(
            {"nombre": "A", "cantidad": "", "unidad": "", "precio": "10"}
        )
        assert errors == []
        assert data["unit"] == "unidad"

    def test_falta_nombre(self):
        _, errors = _adapter().validate_row(
            {"nombre": "", "unidad": "kg", "precio": "10"}
        )
        assert any("nombre" in e.lower() for e in errors)

    def test_falta_precio(self):
        _, errors = _adapter().validate_row(
            {"nombre": "A", "unidad": "kg", "precio": ""}
        )
        assert any("precio" in e.lower() for e in errors)

    def test_precio_no_numerico(self):
        _, errors = _adapter().validate_row(
            {"nombre": "A", "unidad": "kg", "precio": "abc"}
        )
        assert any("precio" in e.lower() for e in errors)

    def test_nombre_muy_largo(self):
        _, errors = _adapter().validate_row(
            {"nombre": "x" * 121, "unidad": "kg", "precio": "10"}
        )
        assert any("120" in e for e in errors)

    def test_unidad_invalida(self):
        _, errors = _adapter().validate_row(
            {"nombre": "A", "unidad": "onza", "precio": "10"}
        )
        assert any("unidad" in e.lower() for e in errors)

    def test_cantidad_negativa(self):
        _, errors = _adapter().validate_row(
            {"nombre": "A", "cantidad": "-1", "unidad": "kg", "precio": "10"}
        )
        assert errors


class TestRoundTrip:
    def test_plantilla_pasa_la_validacion(self):
        adapter = _adapter()
        text = adapter.template()
        delimiter = detect_delimiter(text)
        headers, rows = parse_csv(text, delimiter)
        assert headers == adapter.columns
        dicts = rows_to_dicts(headers, rows)
        assert len(dicts) >= 2
        for d in dicts:
            _, errors = adapter.validate_row(d)
            assert errors == []


class TestColumnas:
    def test_coincide_set_orden_irrelevante(self):
        adapter = _adapter()
        check_columns(adapter.columns, ["precio", "nombre", "unidad", "cantidad"])

    def test_columna_desconocida(self):
        adapter = _adapter()
        try:
            check_columns(
                adapter.columns, ["nombre", "cantidad", "unidad", "precio", "costo"]
            )
        except ColumnMismatchError as e:
            assert e.extra == ["costo"]
        else:
            raise AssertionError("deberia lanzar ColumnMismatchError")

    def test_columna_faltante(self):
        adapter = _adapter()
        try:
            check_columns(adapter.columns, ["nombre", "cantidad", "unidad"])
        except ColumnMismatchError as e:
            assert "precio" in e.missing
        else:
            raise AssertionError("deberia lanzar ColumnMismatchError")

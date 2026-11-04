"""Tests de parsers puros de CSV (T-CSV-2, RF-CSV-10, RNF-CSV-08).

Sin I/O ni DB: encoding (BOM/UTF-8/Latin-1), deteccion de separador (; vs ,)
y parsing de filas. El parser debe tolerar los dos separadores mas usados en
Argentina y los dos encodings mas comunes en planillas de Excel.
"""
from api.v1.imports.parsers import (
    decode_text,
    detect_delimiter,
    detect_encoding,
    parse_csv,
    rows_to_dicts,
)


class TestEncoding:
    def test_bom_utf8(self):
        raw = "nombre;precio\na;1\n".encode("utf-8-sig")
        assert detect_encoding(raw) == "utf-8-sig"

    def test_utf8_puro(self):
        assert detect_encoding("nombre;precio\na;1\n".encode("utf-8")) == "utf-8"

    def test_utf8_con_acento(self):
        raw = "Limón;1\n".encode("utf-8")
        assert detect_encoding(raw) == "utf-8"

    def test_latin1(self):
        # 0xE9 = é en Latin-1 (inválido como UTF-8).
        assert detect_encoding(b"caf\xe9;1\n") == "latin-1"

    def test_decode_text_retira_bom(self):
        raw = "nombre\na\n".encode("utf-8-sig")
        text, enc = decode_text(raw)
        assert enc == "utf-8-sig"
        assert text.startswith("nombre")  # sin BOM


class TestDelimitador:
    def test_punto_y_coma(self):
        assert detect_delimiter("nombre;cantidad;unidad;precio\n") == ";"

    def test_coma(self):
        assert detect_delimiter("nombre,cantidad,unidad,precio\n") == ","

    def test_mayoria_se_imponen(self):
        assert detect_delimiter("a;b,c;d\n") == ";"

    def test_vacio_por_defecto_separador(self):
        assert detect_delimiter("") == ";"
        assert detect_delimiter("una\n") == ";"


class TestParseCsv:
    def test_encabezado_y_filas(self):
        text = "nombre;cantidad;unidad;precio\nHarina;1;kg;1200\nLeche;2;L;1500\n"
        headers, rows = parse_csv(text, ";")
        assert headers == ["nombre", "cantidad", "unidad", "precio"]
        assert rows == [["Harina", "1", "kg", "1200"], ["Leche", "2", "L", "1500"]]

    def test_encabezado_con_espacios(self):
        headers, _ = parse_csv(" nombre ; precio \nA;1\n", ";")
        assert headers == ["nombre", "precio"]

    def test_filas_vacias_se_ignoran(self):
        text = "a;b\nA;1\n\n  \nC;3\n"
        headers, rows = parse_csv(text, ";")
        assert rows == [["A", "1"], ["C", "3"]]

    def test_celdas_citadas_con_separador_dentro(self):
        text = 'a;b\n"Harina 000, fina";1\n'
        headers, rows = parse_csv(text, ";")
        assert rows == [["Harina 000, fina", "1"]]

    def test_vacio(self):
        headers, rows = parse_csv("", ";")
        assert headers == []
        assert rows == []

    def test_coma_como_separador(self):
        headers, rows = parse_csv("nombre,precio\nA,1\n", ",")
        assert headers == ["nombre", "precio"]
        assert rows == [["A", "1"]]


class TestRowsToDicts:
    def test_mapeo(self):
        headers = ["a", "b", "c"]
        rows = [["1", "2", "3"]]
        assert rows_to_dicts(headers, rows) == [{"a": "1", "b": "2", "c": "3"}]

    def test_falta_celda_da_vacio(self):
        assert rows_to_dicts(["a", "b", "c"], [["1"]]) == [{"a": "1", "b": "", "c": ""}]

    def test_sobran_celdas_se_descartan(self):
        assert rows_to_dicts(["a", "b"], [["1", "2", "3"]]) == [{"a": "1", "b": "2"}]

    def test_espacios_en_valores(self):
        assert rows_to_dicts(["a", "b"], [[" x ", " y "]]) == [{"a": "x", "b": "y"}]

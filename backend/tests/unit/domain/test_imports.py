from datetime import timedelta

import pytest

from domain.imports import (
    STAGING_TTL,
    ColumnMismatchError,
    ImportRow,
    ImportRowStatus,
    ImportSession,
    ImportStatus,
    check_columns,
)


class TestEstados:
    def test_estado_de_sesion(self):
        assert ImportStatus.RECEIVED.value == "received"
        assert ImportStatus.IN_REVIEW.value == "in_review"
        assert ImportStatus.CONFIRMED.value == "confirmed"
        assert ImportStatus.DISCARDED.value == "discarded"

    def test_estado_de_fila(self):
        assert ImportRowStatus.VALID.value == "valid"
        assert ImportRowStatus.INVALID.value == "invalid"

    def test_fila_validas_no_tiene_errores(self):
        row = ImportRow(row_number=1, status=ImportRowStatus.VALID, data={"a": "1"}, errors=[])
        assert row.errors == []
        assert row.row_number == 1


class TestSesionYTotales:
    def test_create_calcula_invalidas_y_estado_inicial(self):
        s = ImportSession.create(
            tenant_id="t",
            user_id="u",
            entity="ingredients",
            filename="a.csv",
            delimiter=";",
            encoding="utf-8-sig",
            template_columns=["nombre", "cantidad", "unidad", "precio"],
            total_rows=10,
            valid_rows=8,
        )
        assert s.invalid_rows == 2
        assert s.total_rows == 10
        assert s.valid_rows == 8
        assert s.status is ImportStatus.RECEIVED
        assert s.confirmed_at is None
        assert s.id

    def test_totales(self):
        s = ImportSession.create(
            "t", "u", "ingredients", "a.csv", ";", "utf-8", ["a"], 5, 5
        )
        assert s.totals() == (5, 5, 0)

    def test_ttl_es_siete_dias(self):
        assert STAGING_TTL == timedelta(days=7)

    def test_is_expired_dentro_del_ttl(self):
        s = ImportSession.create("t", "u", "ingredients", "a.csv", ";", "utf-8", ["a"], 1, 1)
        assert not s.is_expired(s.created_at + timedelta(hours=1))
        assert not s.is_expired(s.created_at + timedelta(days=6, hours=23))

    def test_is_expired_fuera_del_ttl(self):
        s = ImportSession.create("t", "u", "ingredients", "a.csv", ";", "utf-8", ["a"], 1, 1)
        assert s.is_expired(s.created_at + timedelta(days=7, hours=1))


class TestValidacionDeColumnas:
    def test_coincide_sin_importar_orden(self):
        check_columns(["nombre", "cantidad", "unidad", "precio"],
                      ["precio", "unidad", "cantidad", "nombre"])

    def test_columna_faltante(self):
        with pytest.raises(ColumnMismatchError) as exc:
            check_columns(["a", "b", "c"], ["a", "b"])
        assert exc.value.missing == ["c"]
        assert exc.value.extra == []

    def test_columna_sobrante(self):
        with pytest.raises(ColumnMismatchError) as exc:
            check_columns(["a", "b"], ["a", "b", "x"])
        assert exc.value.missing == []
        assert exc.value.extra == ["x"]

    def test_falta_y_sobra_a_la_vez(self):
        with pytest.raises(ColumnMismatchError) as exc:
            check_columns(["a", "b"], ["a", "x"])
        assert exc.value.missing == ["b"]
        assert exc.value.extra == ["x"]

"""Parsing tolerante de la importación por lista (RF-P2-07)."""
from decimal import Decimal

import pytest

from domain.ingredients_import import ImportLineError, parse_import_line


def test_basic_three_fields():
    parsed = parse_import_line("harina 0000, 5, 2800")
    assert parsed.name == "harina 0000"
    assert parsed.qty == Decimal("5")
    assert parsed.price_per_unit == Decimal("2800")
    assert parsed.unit == "unidad"


def test_qty_with_attached_unit():
    parsed = parse_import_line("aceite de girasol, 1 L, 300")
    assert parsed.unit == "L"
    assert parsed.qty == Decimal("1")
    assert parsed.price_per_unit == Decimal("300")


def test_comma_decimal_with_unit():
    # Convención argentina: coma como separador decimal.
    parsed = parse_import_line("azúcar, 1,5 kg, 1200")
    assert parsed.qty == Decimal("1.5")
    assert parsed.unit == "kg"
    assert parsed.price_per_unit == Decimal("1200")


def test_thousands_dot_with_decimal_comma():
    parsed = parse_import_line("leche, 1.000,5 L, 250")
    assert parsed.qty == Decimal("1000.5")
    assert parsed.unit == "L"


def test_four_fields_with_explicit_unit():
    parsed = parse_import_line("levadura, 2, g, 500")
    assert parsed.name == "levadura"
    assert parsed.qty == Decimal("2")
    assert parsed.unit == "g"
    assert parsed.price_per_unit == Decimal("500")


def test_unit_case_insensitive_canonical():
    parsed = parse_import_line("harina, 5 kg, 2800")
    assert parsed.unit == "kg"


def test_whitespace_tolerant():
    parsed = parse_import_line("  manteca  ,  2 ,  3500 ")
    assert parsed.name == "manteca"
    assert parsed.qty == Decimal("2")
    assert parsed.price_per_unit == Decimal("3500")


def test_too_few_fields_raises():
    with pytest.raises(ImportLineError, match="3 campos"):
        parse_import_line("harina, 5")


def test_too_many_fields_raises():
    with pytest.raises(ImportLineError, match="3 campos"):
        parse_import_line("harina, 5, 2800, extra, campo")


def test_empty_name_raises():
    with pytest.raises(ImportLineError, match="nombre vacio"):
        parse_import_line(", 5, 2800")


def test_non_numeric_qty_raises():
    with pytest.raises(ImportLineError, match="cantidad"):
        parse_import_line("harina, abc, 2800")


def test_non_numeric_price_raises():
    with pytest.raises(ImportLineError, match="precio"):
        parse_import_line("harina, 5, gratis")


def test_negative_qty_raises():
    with pytest.raises(ImportLineError, match="negativo"):
        parse_import_line("harina, -5, 2800")


def test_invalid_unit_raises():
    with pytest.raises(ImportLineError, match="unidad"):
        parse_import_line("harina, 5 onzas, 2800")

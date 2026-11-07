"""Tests del renderer ReportLab del presupuesto (DTO plano).

El renderer recibe un ``BudgetPdfRequest`` (no el dominio ``Budget``): los
tests construyen el DTO con datos planos replicando la misma matematica de
precios de ``derive_budget_items`` (margen 100%, IVA 21%).

Verificaciones clave (P9): snapshot del cliente en el PDF, NUNCA
costo/ganancia/margen, y escaping de nombres hostiles.
"""
import datetime
import io
from decimal import Decimal

import pytest

from pdfgenerator.renderers import build_budget_pdf, format_money_peso
from pdfgenerator.schemas import BudgetItemRequest, BudgetPdfRequest


def _selling(unit_cost: Decimal, margin_pct: Decimal, qty: int):
    unit = (unit_cost * (Decimal("100") + margin_pct) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    line = (unit * qty).quantize(Decimal("0.01"))
    return unit, line


def _req(
    qty: int = 2,
    cost: Decimal = Decimal("775"),
    customer: str = "María Fernanda",
    business: str = "Toscana Pastry",
    footer: str = "",
    seq: str = "#00001",
    version: int = 1,
    delivery: str | None = None,
) -> BudgetPdfRequest:
    """DTO equivalente a lo que core-api enviaria para un presupuesto tipico."""
    margin = Decimal("100")
    u1, l1 = _selling(cost, margin, qty)
    u2, l2 = _selling(Decimal("450"), margin, 1)
    subtotal = l1 + l2
    total = (subtotal * (Decimal("100") + Decimal("21")) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    return BudgetPdfRequest(
        seq=seq,
        version=version,
        created_at=datetime.datetime(2026, 11, 2, 10, 0, 0),
        customer_name=customer,
        customer_phone="5493571234567",
        delivery_address=delivery,
        items=[
            BudgetItemRequest(product_name="Torta de Limón", qty=qty,
                              unit_selling=u1, line_selling=l1),
            BudgetItemRequest(product_name="Brownie de Chispas", qty=1,
                              unit_selling=u2, line_selling=l2),
        ],
        subtotal=subtotal,
        total=total,
        iva_pct=Decimal("21"),
        business_name=business,
        footer_text=footer,
    )


def _extract(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.replace("\ufb01", "fi")


class TestFormatMoneyPeso:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1550", "$1.550,00"),
            ("0", "$0,00"),
            ("1234567.5", "$1.234.567,50"),
            ("1550.005", "$1.550,01"),
            ("-1550", "-$1.550,00"),
        ],
    )
    def test_formato_es_ar(self, raw, expected):
        assert format_money_peso(Decimal(raw)) == expected


class TestBuildBudgetPdf:
    def test_pdf_valido_con_snapshot_del_cliente(self):
        pdf = build_budget_pdf(_req())
        assert pdf[:4] == b"%PDF"
        text = _extract(pdf)
        assert "Toscana Pastry" in text
        assert "PRESUPUESTO #00001" in text
        assert "María Fernanda" in text
        assert "Torta de Limón" in text
        assert "$1.550,00" in text
        assert "Brownie de Chispas" in text
        assert "$900,00" in text
        assert "$4.000,00" in text
        assert "$4.840,00" in text
        assert "IVA" in text

    def test_el_pdf_no_contiene_costo_ganancia_ni_margen(self):
        pdf = build_budget_pdf(_req())
        text = _extract(pdf).lower()
        assert "costo" not in text
        assert "ganancia" not in text
        assert "margen" not in text
        assert "$775,00" not in text
        assert "$2.000,00" not in text

    def test_branding_de_negocio(self):
        pdf = build_budget_pdf(_req(business="La Panadería",
                                    footer="Pedidos: (0357) 123-4567"))
        text = _extract(pdf)
        assert "La Panadería" in text
        assert "Pedidos: (0357) 123-4567" in text

    def test_cantidad_cambiada_cambia_el_pdf(self):
        a = build_budget_pdf(_req(qty=2))
        b = build_budget_pdf(_req(qty=3))
        assert a != b


class TestPdfMarkupEscaping:
    HOSTILE = [
        "Dulces & Tortas",
        "Torta <3",
        "a > b",
        '<img src="file:///etc/passwd"/>',
        "<b>negrita sin cerrar",
    ]

    @pytest.mark.parametrize("name", HOSTILE)
    def test_nombre_se_renderiza_literal(self, name):
        unit, line = _selling(Decimal("100"), Decimal("100"), 1)
        subtotal = line
        total = (subtotal * Decimal("1.21")).quantize(Decimal("0.01"))
        req = BudgetPdfRequest(
            seq="#00001",
            version=1,
            created_at=datetime.datetime(2026, 11, 2, 10, 0, 0),
            customer_name=name,
            customer_phone="5493571234567",
            delivery_address=None,
            items=[BudgetItemRequest(product_name=name, qty=1,
                                     unit_selling=unit, line_selling=line)],
            subtotal=subtotal,
            total=total,
            iva_pct=Decimal("21"),
            business_name=name,
            footer_text=name,
        )
        pdf = build_budget_pdf(req)
        assert pdf[:4] == b"%PDF"
        text = " ".join(_extract(pdf).split())
        assert " ".join(name.split()) in text

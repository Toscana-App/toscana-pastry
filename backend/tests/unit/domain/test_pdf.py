"""dominio.pdf (Fase 8, P9): builder ReportLab.

Verificaciones clave (seguridad de P9):
- El PDF es real (%PDF) y el texto extraído contiene el snapshot del
  cliente (productos, precios, total).
- El texto NUNCA contiene costo/ganancia/margen: el documento que ve el
  cliente no expone números internos.
- Hash de contenido: estable para el mismo documento, cambia con el
  contenido, e invariante ante cambios de costo (que no se renderizan).
"""
from decimal import Decimal
import pytest

from domain.budgets import Budget, derive_budget_items
from domain.pdf import (
    budget_content_hash,
    build_budget_pdf,
    format_money_peso,
)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Texto extraído de un PDF (pypdf). Solo para tests."""
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _budget(
    unit_cost: Decimal = Decimal("775"),
    qty: int = 2,
    business: str = "Toscana Pastry",
) -> Budget:
    items, _totals = derive_budget_items(
        (
            ("p1", "Torta de Limón", qty, unit_cost, None),
            ("p2", "Brownie de Chispas", 1, Decimal("450"), None),
        ),
        Decimal("100"),
    )
    return Budget(
        customer_id="c1",
        customer_name="María Fernanda",
        customer_phone="5493571234567",
        items=items,
        margin_pct=Decimal("100"),
        seq="#00001",
        version=1,
        status="enviado",
    )


class TestFormatMoneyPeso:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1550", "$1.550,00"),
            ("0", "$0,00"),
            ("1234567.5", "$1.234.567,50"),
            ("1550.005", "$1.550,01"),  # redondeo a centavos
            ("-1550", "-$1.550,00"),
        ],
    )
    def test_formato_es_ar(self, raw, expected):
        assert format_money_peso(Decimal(raw)) == expected


class TestBuildBudgetPdf:
    def test_pdf_valido_con_snapshot_del_cliente(self):
        pdf = build_budget_pdf(_budget(), "Toscana Pastry", "")
        assert pdf[:4] == b"%PDF"
        text = extract_pdf_text(pdf)
        # Identidad + secuencia.
        assert "Toscana Pastry" in text
        assert "PRESUPUESTO #00001" in text
        # Cliente.
        assert "María Fernanda" in text
        # Items con precios de venta (costo 775, margen 100% -> 1.550 c/u).
        assert "Torta de Limón" in text
        assert "$1.550,00" in text
        assert "Brownie de Chispas" in text
        assert "$900,00" in text
        # Totales: subtotal 4.000 + IVA 21% = 4.840.
        assert "$4.000,00" in text
        assert "$4.840,00" in text
        assert "IVA" in text

    def test_el_pdf_no_contiene_costo_ganancia_ni_margen(self):
        """Seguridad de P9: los números internos no existen en el
        documento, ni como dato ni como palabra."""
        pdf = build_budget_pdf(_budget(), "Toscana Pastry", "")
        text = extract_pdf_text(pdf).lower()
        assert "costo" not in text
        assert "ganancia" not in text
        assert "margen" not in text
        # El costo unitario (775) y la ganancia (2.000) no aparecen.
        assert "$775,00" not in text
        assert "$2.000,00" not in text

    def test_branding_de_negocio(self):
        pdf = build_budget_pdf(
            _budget(), "La Panadería", "Pedidos: (0357) 123-4567"
        )
        text = extract_pdf_text(pdf)
        assert "La Panadería" in text
        assert "Pedidos: (0357) 123-4567" in text

    def test_cantidad_cambiada_cambia_el_pdf(self):
        a = build_budget_pdf(_budget(qty=2), "T", "")
        b = build_budget_pdf(_budget(qty=3), "T", "")
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
    def test_nombre_de_cliente_y_producto_se_renderizan_literales(self, name):
        items, _ = derive_budget_items(
            (("p1", name, 1, Decimal("100"), None),), Decimal("100")
        )
        budget = Budget(
            customer_id="c1",
            customer_name=name,
            customer_phone="5493571234567",
            items=items,
            margin_pct=Decimal("100"),
            seq="#00001",
            version=1,
            status="enviado",
        )
        pdf = build_budget_pdf(budget, name, name)
        assert pdf[:4] == b"%PDF"
        text = extract_pdf_text(pdf).replace("\n", " ")
        assert " ".join(name.split()) in " ".join(text.split())


class TestBudgetContentHash:
    def test_estable_para_el_mismo_documento(self):
        h1 = budget_content_hash(_budget(), "T", "")
        h2 = budget_content_hash(_budget(), "T", "")
        assert h1 == h2

    def test_cambia_cuando_cambia_el_precio(self):
        h1 = budget_content_hash(_budget(), "T", "")
        h2 = budget_content_hash(_budget(unit_cost=Decimal("999")), "T", "")
        assert h1 != h2

    def test_cambia_cuando_cambia_el_branding(self):
        h1 = budget_content_hash(_budget(), "Toscana Pastry", "")
        h2 = budget_content_hash(_budget(), "Otro Nombre", "")
        assert h1 != h2

    def test_invariante_al_cambiar_el_costo_interno(self):
        """El hash cubre solo lo que se renderiza: con precio de venta
        idéntico (override manual), un costo interno distinto no cambia
        el documento ni el hash."""
        def with_cost(c):
            items, _t = derive_budget_items(
                (("p1", "Torta de Limón", 2, c, Decimal("1550")),),
                Decimal("100"),
            )
            return Budget(
                customer_id="c1",
                customer_name="M",
                customer_phone="5491155556789",
                items=items,
                margin_pct=Decimal("100"),
                seq="#00001",
                version=1,
            )

        h1 = budget_content_hash(with_cost(Decimal("775")), "T", "")
        h2 = budget_content_hash(with_cost(Decimal("999")), "T", "")
        assert h1 == h2

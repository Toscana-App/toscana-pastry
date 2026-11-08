"""dominio.pdf (Fase 8, P9): helpers de formato y hash de contenido.

El builder del PDF (ReportLab) y el escape de markup viven en el servicio
pdfgenerator (ADR-0001). Aquí se prueba solo lo que sigue siendo
responsabilidad de core-api:
- format_money_peso: formato es-AR de montos (lo usa el envío por WhatsApp).
- budget_content_hash: hash estable del contenido visible, invariante ante
  costos internos que no se renderizan.
"""
from decimal import Decimal
import pytest

from domain.budgets import Budget, derive_budget_items
from domain.pdf import budget_content_hash, format_money_peso


def _budget(unit_cost: Decimal = Decimal("775"), qty: int = 2) -> Budget:
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

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
            ("1550.005", "$1.550,01"),
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

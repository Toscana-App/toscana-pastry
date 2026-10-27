"""Unit tests for the pure dashboard metrics (RF-P3CC-05).

`build_dashboard_stats` is a frozen-dataclass / Decimal pure function
(styled after `domain/calc_product.py`): no I/O, no float on money.
Expected values are hand-computed literals from the spec, not
re-derived from the implementation.
"""

from decimal import Decimal

from domain.calc_dashboard import (
    BottomByMarginItem,
    DashboardStats,
    TopByPriceItem,
    build_dashboard_stats,
)
from domain.calc_product import CalcProduct, CalcProductCosts


def _costs(total: str, final: str) -> CalcProductCosts:
    return CalcProductCosts(
        product_total_cost=Decimal(total),
        profit_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        adjusted_profit_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        final_sale_price=Decimal(final),
    )


def _product(name: str, margin: str, total: str, final: str, pid: str) -> tuple:
    """(CalcProduct, CalcProductCosts) pair for the pure function input."""
    return (
        CalcProduct(name=name, margin_percent=Decimal(margin), id=pid),
        _costs(total, final),
    )


class TestCounts:
    def test_counts_read_straight_from_status_dicts(self):
        """Material and product counts come from the persisted derived
        statuses; `archived` is intentionally absent from the response."""
        stats = build_dashboard_stats(
            {"active": 7, "incomplete": 3},
            {"draft": 2, "active": 5, "archived": 4},
            [],
        )
        assert stats.active_materials == 7
        assert stats.incomplete_materials == 3
        assert stats.active_products == 5
        assert stats.draft_products == 2
        # No archived field leaks into the response.
        assert not hasattr(stats, "archived_products")

    def test_missing_keys_default_to_zero(self):
        stats = build_dashboard_stats({}, {}, [])
        assert stats.active_materials == 0
        assert stats.incomplete_materials == 0
        assert stats.active_products == 0
        assert stats.draft_products == 0


class TestAverages:
    def test_averages_quantized_to_cents(self):
        """Promedio Decimal sobre los activos, cuantizado a centavos con
        ROUND_HALF_UP; serializado a str."""
        active = [
            _product("A", "0", "100.00", "170.00", "p1"),
            _product("B", "0", "200.00", "339.99", "p2"),
            _product("C", "0", "300.00", "510.00", "p3"),
        ]
        stats = build_dashboard_stats({"active": 3}, {"active": 3}, active)
        # cost: (100 + 200 + 300) / 3 = 200.00
        assert stats.avg_product_cost == Decimal("200.00")
        # final: (170.00 + 339.99 + 510.00) / 3 = 1019.99 / 3 = 339.9966 -> 340.00
        assert stats.avg_final_price == Decimal("340.00")

    def test_average_uses_half_up_rounding(self):
        """(10.00 + 10.01) / 2 = 10.005 -> ROUND_HALF_UP -> 10.01 (no
        banker's rounding)."""
        active = [
            _product("A", "0", "10.00", "10.00", "p1"),
            _product("B", "0", "10.01", "10.01", "p2"),
        ]
        stats = build_dashboard_stats({"active": 2}, {"active": 2}, active)
        assert stats.avg_product_cost == Decimal("10.01")
        assert stats.avg_final_price == Decimal("10.01")

    def test_zero_active_products_gives_zero(self):
        """Paridad legacy `: 0`: 0 activos -> Decimal('0.00'), sin
        division por cero."""
        stats = build_dashboard_stats({"active": 0}, {"active": 0}, [])
        assert stats.avg_product_cost == Decimal("0.00")
        assert stats.avg_final_price == Decimal("0.00")


class TestTopByPrice:
    def test_top_by_price_desc_limit_five(self):
        """Top 5 por final_sale_price desc; con 6 activos se trunca a 5."""
        active = [
            _product(f"P{i}", "0", "10.00", str(100 - i * 10) + ".00", f"p{i}")
            for i in range(6)
        ]
        # finals: P0=100.00 (mayor) ... P5=50.00 (menor, queda fuera).
        stats = build_dashboard_stats({"active": 6}, {"active": 6}, active)
        assert len(stats.top_by_price) == 5
        assert [item.name for item in stats.top_by_price] == [
            "P0",
            "P1",
            "P2",
            "P3",
            "P4",
        ]
        assert [item.final_sale_price for item in stats.top_by_price] == [
            Decimal("100.00"),
            Decimal("90.00"),
            Decimal("80.00"),
            Decimal("70.00"),
            Decimal("60.00"),
        ]
        # items conservan id + margin_percent.
        assert isinstance(stats.top_by_price[0], TopByPriceItem)
        assert stats.top_by_price[0].id == "p0"
        assert stats.top_by_price[0].margin_percent == Decimal("0")

    def test_fewer_than_five_returns_shorter_list(self):
        active = [
            _product("A", "0", "10.00", "50.00", "p1"),
            _product("B", "0", "10.00", "60.00", "p2"),
        ]
        stats = build_dashboard_stats({"active": 2}, {"active": 2}, active)
        assert [item.name for item in stats.top_by_price] == ["B", "A"]

    def test_ties_broken_by_name_asc(self):
        active = [
            _product("Zebra", "0", "10.00", "50.00", "p1"),
            _product("Alpha", "0", "10.00", "50.00", "p2"),
            _product("Mango", "0", "10.00", "50.00", "p3"),
        ]
        stats = build_dashboard_stats({"active": 3}, {"active": 3}, active)
        assert [item.name for item in stats.top_by_price] == [
            "Alpha",
            "Mango",
            "Zebra",
        ]


class TestBottomByMargin:
    def test_bottom_by_margin_asc_limit_five(self):
        """Bottom 5 por margin_percent asc; con 6 activos se trunca a 5."""
        active = [
            _product(f"P{i}", str(i * 10), "10.00", "50.00", f"p{i}") for i in range(6)
        ]
        # margins: P0=0 (menor) ... P5=50 (mayor, queda fuera).
        stats = build_dashboard_stats({"active": 6}, {"active": 6}, active)
        assert len(stats.bottom_by_margin) == 5
        assert [item.name for item in stats.bottom_by_margin] == [
            "P0",
            "P1",
            "P2",
            "P3",
            "P4",
        ]
        assert [item.margin_percent for item in stats.bottom_by_margin] == [
            Decimal("0"),
            Decimal("10"),
            Decimal("20"),
            Decimal("30"),
            Decimal("40"),
        ]
        # items conservan id + product_total_cost.
        assert isinstance(stats.bottom_by_margin[0], BottomByMarginItem)
        assert stats.bottom_by_margin[0].id == "p0"
        assert stats.bottom_by_margin[0].product_total_cost == Decimal("10.00")

    def test_fewer_than_five_returns_shorter_list(self):
        active = [
            _product("A", "50", "100.00", "50.00", "p1"),
            _product("B", "10", "200.00", "60.00", "p2"),
            _product("C", "30", "300.00", "70.00", "p3"),
        ]
        stats = build_dashboard_stats({"active": 3}, {"active": 3}, active)
        assert [item.name for item in stats.bottom_by_margin] == [
            "B",
            "C",
            "A",
        ]

    def test_ties_broken_by_name_asc(self):
        active = [
            _product("Zebra", "20", "10.00", "50.00", "p1"),
            _product("Alpha", "20", "10.00", "50.00", "p2"),
        ]
        stats = build_dashboard_stats({"active": 2}, {"active": 2}, active)
        assert [item.name for item in stats.bottom_by_margin] == [
            "Alpha",
            "Zebra",
        ]


class TestShape:
    def test_returns_frozen_dataclass(self):
        stats = build_dashboard_stats({"active": 1}, {"active": 1}, [])
        assert isinstance(stats, DashboardStats)
        try:
            stats.active_materials = 99  # type: ignore[misc]
            raised = False
        except Exception:
            raised = True
        assert raised, "DashboardStats debe ser frozen"

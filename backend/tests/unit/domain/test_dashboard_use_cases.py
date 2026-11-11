from datetime import date
from decimal import Decimal

import pytest

from domain.dashboard import (
    DashboardPeriod,
    Granularity,
    InvalidDashboardPeriodError,
    InvalidTopProductsLimitError,
    PaymentSplit,
    SalesPoint,
    SalesTotals,
    StatusCount,
    TopProduct,
)
from domain.repositories import DashboardRepository
from domain.use_cases.get_orders_by_status import GetOrdersByStatus
from domain.use_cases.get_payment_method_split import GetPaymentMethodSplit
from domain.use_cases.get_sales_summary import GetSalesSummary
from domain.use_cases.get_sales_time_series import GetSalesTimeSeries
from domain.use_cases.get_top_products import GetTopProducts

TODAY = date(2026, 5, 20)


def _clock() -> date:
    return TODAY


class FakeDashboardRepository(DashboardRepository):

    def __init__(self) -> None:
        self.totals = SalesTotals(Decimal("0"), 0, Decimal("0"), 0)
        self.points: list[SalesPoint] = []
        self.statuses: list[StatusCount] = []
        self.products: list[TopProduct] = []
        self.payments: list[PaymentSplit] = []
        self.calls: list[tuple] = []

    async def sales_totals(self, period: DashboardPeriod) -> SalesTotals:
        self.calls.append(("totals", period))
        return self.totals

    async def sales_series(
        self, period: DashboardPeriod, granularity: Granularity
    ) -> list[SalesPoint]:
        self.calls.append(("series", period, granularity))
        return self.points

    async def status_counts(self, period: DashboardPeriod) -> list[StatusCount]:
        self.calls.append(("statuses", period))
        return self.statuses

    async def top_products(
        self, period: DashboardPeriod, limit: int
    ) -> list[TopProduct]:
        self.calls.append(("top", period, limit))
        return self.products

    async def payment_split(self, period: DashboardPeriod) -> list[PaymentSplit]:
        self.calls.append(("payments", period))
        return self.payments


@pytest.fixture
def repo() -> FakeDashboardRepository:
    return FakeDashboardRepository()


class TestGetSalesSummary:
    async def test_computes_average_ticket_and_pending(self, repo):
        repo.totals = SalesTotals(Decimal("1000"), 4, Decimal("600"), 2)
        summary = await GetSalesSummary(repo, _clock).execute(
            date(2026, 5, 1), date(2026, 5, 20)
        )
        assert summary.revenue == Decimal("1000")
        assert summary.orders_count == 4
        assert summary.average_ticket == Decimal("250.00")
        assert summary.paid_revenue == Decimal("600")
        assert summary.pending_revenue == Decimal("400")
        assert summary.cancelled_count == 2

    async def test_no_orders_gives_zero_average(self, repo):
        summary = await GetSalesSummary(repo, _clock).execute(None, None)
        assert summary.average_ticket == Decimal("0")
        assert summary.pending_revenue == Decimal("0")

    async def test_average_rounds_half_up_to_cents(self, repo):
        repo.totals = SalesTotals(Decimal("100"), 3, Decimal("0"), 0)
        summary = await GetSalesSummary(repo, _clock).execute(None, None)
        assert summary.average_ticket == Decimal("33.33")

    async def test_default_period_is_last_thirty_days(self, repo):
        await GetSalesSummary(repo, _clock).execute(None, None)
        period = repo.calls[0][1]
        assert period == DashboardPeriod(date(2026, 4, 21), TODAY)

    async def test_invalid_period_never_reaches_repository(self, repo):
        with pytest.raises(InvalidDashboardPeriodError):
            await GetSalesSummary(repo, _clock).execute(
                date(2026, 5, 20), date(2026, 5, 1)
            )
        assert repo.calls == []


class TestGetSalesTimeSeries:
    async def test_zero_fills_missing_days(self, repo):
        repo.points = [
            SalesPoint(date(2026, 5, 2), Decimal("300"), 2),
        ]
        series = await GetSalesTimeSeries(repo, _clock).execute(
            date(2026, 5, 1), date(2026, 5, 3), Granularity.DAY
        )
        assert series == [
            SalesPoint(date(2026, 5, 1), Decimal("0"), 0),
            SalesPoint(date(2026, 5, 2), Decimal("300"), 2),
            SalesPoint(date(2026, 5, 3), Decimal("0"), 0),
        ]

    async def test_weekly_buckets_align_to_monday(self, repo):
        repo.points = [SalesPoint(date(2026, 5, 18), Decimal("50"), 1)]
        series = await GetSalesTimeSeries(repo, _clock).execute(
            date(2026, 5, 13), date(2026, 5, 26), Granularity.WEEK
        )
        assert [p.bucket for p in series] == [
            date(2026, 5, 11),
            date(2026, 5, 18),
            date(2026, 5, 25),
        ]
        assert series[1].revenue == Decimal("50")

    async def test_ignores_points_outside_generated_buckets(self, repo):
        repo.points = [SalesPoint(date(2026, 6, 1), Decimal("9"), 1)]
        series = await GetSalesTimeSeries(repo, _clock).execute(
            date(2026, 5, 1), date(2026, 5, 2), Granularity.DAY
        )
        assert all(p.orders_count == 0 for p in series)

    async def test_passes_granularity_to_repository(self, repo):
        await GetSalesTimeSeries(repo, _clock).execute(
            date(2026, 1, 1), date(2026, 3, 1), Granularity.MONTH
        )
        assert repo.calls[0][2] is Granularity.MONTH

    async def test_default_granularity_is_day(self, repo):
        series = await GetSalesTimeSeries(repo, _clock).execute(
            date(2026, 5, 1), date(2026, 5, 2)
        )
        assert len(series) == 2
        assert repo.calls[0][2] is Granularity.DAY

    async def test_invalid_period_rejected(self, repo):
        with pytest.raises(InvalidDashboardPeriodError):
            await GetSalesTimeSeries(repo, _clock).execute(
                date(2026, 5, 3), date(2026, 5, 1)
            )


class TestGetOrdersByStatus:
    async def test_zero_fills_every_known_status_in_workflow_order(self, repo):
        repo.statuses = [StatusCount("confirmado", 3)]
        result = await GetOrdersByStatus(repo, _clock).execute(None, None)
        assert result == [
            StatusCount("nuevo", 0),
            StatusCount("confirmado", 3),
            StatusCount("entregado", 0),
            StatusCount("cancelado", 0),
        ]

    async def test_invalid_period_rejected(self, repo):
        with pytest.raises(InvalidDashboardPeriodError):
            await GetOrdersByStatus(repo, _clock).execute(
                date(2026, 5, 3), date(2026, 5, 1)
            )


class TestGetTopProducts:
    async def test_default_limit_is_five(self, repo):
        await GetTopProducts(repo, _clock).execute(None, None)
        assert repo.calls[0][2] == 5

    async def test_returns_repository_rows(self, repo):
        repo.products = [TopProduct("p1", "Torta", 3, Decimal("900"))]
        result = await GetTopProducts(repo, _clock).execute(None, None, limit=10)
        assert result == repo.products
        assert repo.calls[0][2] == 10

    @pytest.mark.parametrize("limit", [0, -1, 21, 100])
    async def test_limit_out_of_range_rejected(self, repo, limit):
        with pytest.raises(InvalidTopProductsLimitError):
            await GetTopProducts(repo, _clock).execute(None, None, limit=limit)
        assert repo.calls == []

    @pytest.mark.parametrize("limit", [1, 20])
    async def test_limit_bounds_accepted(self, repo, limit):
        await GetTopProducts(repo, _clock).execute(None, None, limit=limit)
        assert repo.calls[0][2] == limit

    async def test_invalid_period_rejected(self, repo):
        with pytest.raises(InvalidDashboardPeriodError):
            await GetTopProducts(repo, _clock).execute(
                date(2026, 5, 3), date(2026, 5, 1)
            )


class TestGetPaymentMethodSplit:
    async def test_returns_repository_rows(self, repo):
        repo.payments = [
            PaymentSplit("cash", 2, Decimal("500")),
            PaymentSplit("mercadopago", 1, Decimal("300")),
        ]
        result = await GetPaymentMethodSplit(repo, _clock).execute(None, None)
        assert result == repo.payments

    async def test_uses_resolved_period(self, repo):
        await GetPaymentMethodSplit(repo, _clock).execute(date(2026, 5, 1), None)
        assert repo.calls[0][1] == DashboardPeriod(date(2026, 5, 1), TODAY)

    async def test_invalid_period_rejected(self, repo):
        with pytest.raises(InvalidDashboardPeriodError):
            await GetPaymentMethodSplit(repo, _clock).execute(
                date(2026, 5, 3), date(2026, 5, 1)
            )

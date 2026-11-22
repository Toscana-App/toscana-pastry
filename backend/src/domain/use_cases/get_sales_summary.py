import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

from domain.dashboard import DashboardPeriod, SalesSummary, local_today
from domain.repositories import DashboardRepository

_CENT = Decimal("0.01")


class GetSalesSummary:

    def __init__(
        self,
        repository: DashboardRepository,
        clock: Callable[[], datetime.date] = local_today,
    ):
        self._repository = repository
        self._clock = clock

    async def execute(
        self, date_from: datetime.date | None, date_to: datetime.date | None
    ) -> SalesSummary:
        period = DashboardPeriod.resolve(date_from, date_to, self._clock())
        totals = await self._repository.sales_totals(period)
        average = (
            (totals.revenue / totals.orders_count).quantize(
                _CENT, rounding=ROUND_HALF_UP
            )
            if totals.orders_count
            else Decimal("0")
        )
        return SalesSummary(
            revenue=totals.revenue,
            orders_count=totals.orders_count,
            average_ticket=average,
            paid_revenue=totals.paid_revenue,
            pending_revenue=totals.revenue - totals.paid_revenue,
            cancelled_count=totals.cancelled_count,
        )

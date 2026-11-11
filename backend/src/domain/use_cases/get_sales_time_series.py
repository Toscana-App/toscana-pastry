import datetime
from decimal import Decimal
from typing import Callable

from domain.dashboard import (
    DashboardPeriod,
    Granularity,
    SalesPoint,
    bucket_starts,
    local_today,
)
from domain.repositories import DashboardRepository


class GetSalesTimeSeries:

    def __init__(
        self,
        repository: DashboardRepository,
        clock: Callable[[], datetime.date] = local_today,
    ):
        self._repository = repository
        self._clock = clock

    async def execute(
        self,
        date_from: datetime.date | None,
        date_to: datetime.date | None,
        granularity: Granularity = Granularity.DAY,
    ) -> list[SalesPoint]:
        period = DashboardPeriod.resolve(date_from, date_to, self._clock())
        points = await self._repository.sales_series(period, granularity)
        by_bucket = {point.bucket: point for point in points}
        return [
            by_bucket.get(start, SalesPoint(start, Decimal("0"), 0))
            for start in bucket_starts(period, granularity)
        ]

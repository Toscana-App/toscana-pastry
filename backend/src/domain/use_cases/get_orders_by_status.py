import datetime
from typing import Callable

from domain.dashboard import DashboardPeriod, StatusCount, local_today
from domain.order import OrderStatus
from domain.repositories import DashboardRepository


class GetOrdersByStatus:

    def __init__(
        self,
        repository: DashboardRepository,
        clock: Callable[[], datetime.date] = local_today,
    ):
        self._repository = repository
        self._clock = clock

    async def execute(
        self, date_from: datetime.date | None, date_to: datetime.date | None
    ) -> list[StatusCount]:
        period = DashboardPeriod.resolve(date_from, date_to, self._clock())
        rows = await self._repository.status_counts(period)
        counts = {row.status: row.orders_count for row in rows}
        return [
            StatusCount(status.value, counts.get(status.value, 0))
            for status in OrderStatus
        ]

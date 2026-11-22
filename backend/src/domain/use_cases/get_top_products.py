import datetime
from typing import Callable

from domain.dashboard import (
    DEFAULT_TOP_PRODUCTS_LIMIT,
    MAX_TOP_PRODUCTS_LIMIT,
    MIN_TOP_PRODUCTS_LIMIT,
    DashboardPeriod,
    InvalidTopProductsLimitError,
    TopProduct,
    local_today,
)
from domain.repositories import DashboardRepository


class GetTopProducts:

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
        limit: int = DEFAULT_TOP_PRODUCTS_LIMIT,
    ) -> list[TopProduct]:
        if not MIN_TOP_PRODUCTS_LIMIT <= limit <= MAX_TOP_PRODUCTS_LIMIT:
            raise InvalidTopProductsLimitError(limit)
        period = DashboardPeriod.resolve(date_from, date_to, self._clock())
        return await self._repository.top_products(period, limit)

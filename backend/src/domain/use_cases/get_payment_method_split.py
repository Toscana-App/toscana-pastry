import datetime
from typing import Callable

from domain.dashboard import DashboardPeriod, PaymentSplit, local_today
from domain.repositories import DashboardRepository


class GetPaymentMethodSplit:

    def __init__(
        self,
        repository: DashboardRepository,
        clock: Callable[[], datetime.date] = local_today,
    ):
        self._repository = repository
        self._clock = clock

    async def execute(
        self, date_from: datetime.date | None, date_to: datetime.date | None
    ) -> list[PaymentSplit]:
        period = DashboardPeriod.resolve(date_from, date_to, self._clock())
        return await self._repository.payment_split(period)

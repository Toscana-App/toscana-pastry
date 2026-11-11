import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 366
DEFAULT_TOP_PRODUCTS_LIMIT = 5
MIN_TOP_PRODUCTS_LIMIT = 1
MAX_TOP_PRODUCTS_LIMIT = 20
BUSINESS_TZ_NAME = "America/Argentina/Buenos_Aires"
BUSINESS_TZ = datetime.timezone(datetime.timedelta(hours=-3), "ART")
_DAYS_IN_WEEK = 7
_MONTHS_IN_YEAR = 12


class Granularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class InvalidDashboardPeriodError(ValueError):

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class InvalidTopProductsLimitError(ValueError):

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__("invalid_limit")


@dataclass(frozen=True)
class DashboardPeriod:

    date_from: datetime.date
    date_to: datetime.date

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise InvalidDashboardPeriodError("date_from_after_date_to")
        if self.days > MAX_PERIOD_DAYS:
            raise InvalidDashboardPeriodError("period_too_long")

    @property
    def days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    @classmethod
    def resolve(
        cls,
        date_from: datetime.date | None,
        date_to: datetime.date | None,
        today: datetime.date,
    ) -> "DashboardPeriod":
        end = date_to if date_to is not None else today
        start = (
            date_from
            if date_from is not None
            else end - datetime.timedelta(days=DEFAULT_PERIOD_DAYS - 1)
        )
        return cls(start, end)


@dataclass(frozen=True)
class SalesTotals:

    revenue: Decimal
    orders_count: int
    paid_revenue: Decimal
    cancelled_count: int


@dataclass(frozen=True)
class SalesSummary:

    revenue: Decimal
    orders_count: int
    average_ticket: Decimal
    paid_revenue: Decimal
    pending_revenue: Decimal
    cancelled_count: int


@dataclass(frozen=True)
class SalesPoint:

    bucket: datetime.date
    revenue: Decimal
    orders_count: int


@dataclass(frozen=True)
class StatusCount:

    status: str
    orders_count: int


@dataclass(frozen=True)
class TopProduct:

    product_id: str
    product_name: str
    quantity: int
    revenue: Decimal


@dataclass(frozen=True)
class PaymentSplit:

    payment_method: str
    orders_count: int
    revenue: Decimal


def local_today(now: datetime.datetime | None = None) -> datetime.date:
    current = now or datetime.datetime.now(datetime.UTC)
    return current.astimezone(BUSINESS_TZ).date()


def period_bounds(
    period: DashboardPeriod,
) -> tuple[datetime.datetime, datetime.datetime]:
    start = datetime.datetime.combine(
        period.date_from, datetime.time.min, tzinfo=BUSINESS_TZ
    )
    end = datetime.datetime.combine(
        period.date_to + datetime.timedelta(days=1),
        datetime.time.min,
        tzinfo=BUSINESS_TZ,
    )
    return start, end


def bucket_start(day: datetime.date, granularity: Granularity) -> datetime.date:
    if granularity is Granularity.WEEK:
        return day - datetime.timedelta(days=day.weekday())
    if granularity is Granularity.MONTH:
        return day.replace(day=1)
    return day


def _next_bucket(start: datetime.date, granularity: Granularity) -> datetime.date:
    if granularity is Granularity.WEEK:
        return start + datetime.timedelta(days=_DAYS_IN_WEEK)
    if granularity is Granularity.MONTH:
        year = start.year + start.month // _MONTHS_IN_YEAR
        month = start.month % _MONTHS_IN_YEAR + 1
        return datetime.date(year, month, 1)
    return start + datetime.timedelta(days=1)


def bucket_starts(
    period: DashboardPeriod, granularity: Granularity
) -> list[datetime.date]:
    current = bucket_start(period.date_from, granularity)
    starts: list[datetime.date] = []
    while current <= period.date_to:
        starts.append(current)
        current = _next_bucket(current, granularity)
    return starts

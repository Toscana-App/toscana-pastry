import datetime

from fastapi import APIRouter, Depends, Query, Response

from api.v1.dashboard.dependencies import get_dashboard_repository
from api.v1.dashboard.schemas import (
    OrdersByStatusResponse,
    PaymentMethodsResponse,
    PaymentSplitResponse,
    SalesPointResponse,
    SalesSeriesResponse,
    StatusCountResponse,
    SummaryResponse,
    TopProductResponse,
    TopProductsResponse,
)
from api.v1.dependencies import require_admin
from data.repositories.sql_dashboard_repository import SQLDashboardRepository
from domain.dashboard import (
    DEFAULT_TOP_PRODUCTS_LIMIT,
    DashboardPeriod,
    Granularity,
    local_today,
)
from domain.use_cases.get_orders_by_status import GetOrdersByStatus
from domain.use_cases.get_payment_method_split import GetPaymentMethodSplit
from domain.use_cases.get_sales_summary import GetSalesSummary
from domain.use_cases.get_sales_time_series import GetSalesTimeSeries
from domain.use_cases.get_top_products import GetTopProducts

CACHE_CONTROL = "private, max-age=30"


def _set_cache_headers(response: Response) -> None:
    response.headers["Cache-Control"] = CACHE_CONTROL


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_admin), Depends(_set_cache_headers)],
)

DateFrom = Query(default=None, description="Inclusive ISO start date (Argentina)")
DateTo = Query(default=None, description="Inclusive ISO end date (Argentina)")


def _period(
    date_from: datetime.date | None, date_to: datetime.date | None
) -> DashboardPeriod:
    return DashboardPeriod.resolve(date_from, date_to, local_today())


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    date_from: datetime.date | None = DateFrom,
    date_to: datetime.date | None = DateTo,
    repository: SQLDashboardRepository = Depends(get_dashboard_repository),
) -> SummaryResponse:
    period = _period(date_from, date_to)
    summary = await GetSalesSummary(repository).execute(
        period.date_from, period.date_to
    )
    return SummaryResponse(
        date_from=period.date_from, date_to=period.date_to, **vars(summary)
    )


@router.get("/sales-series", response_model=SalesSeriesResponse)
async def get_sales_series(
    date_from: datetime.date | None = DateFrom,
    date_to: datetime.date | None = DateTo,
    granularity: Granularity = Query(default=Granularity.DAY),
    repository: SQLDashboardRepository = Depends(get_dashboard_repository),
) -> SalesSeriesResponse:
    period = _period(date_from, date_to)
    points = await GetSalesTimeSeries(repository).execute(
        period.date_from, period.date_to, granularity
    )
    return SalesSeriesResponse(
        date_from=period.date_from,
        date_to=period.date_to,
        granularity=granularity,
        points=[SalesPointResponse(**vars(point)) for point in points],
    )


@router.get("/orders-by-status", response_model=OrdersByStatusResponse)
async def get_orders_by_status(
    date_from: datetime.date | None = DateFrom,
    date_to: datetime.date | None = DateTo,
    repository: SQLDashboardRepository = Depends(get_dashboard_repository),
) -> OrdersByStatusResponse:
    period = _period(date_from, date_to)
    items = await GetOrdersByStatus(repository).execute(
        period.date_from, period.date_to
    )
    return OrdersByStatusResponse(
        date_from=period.date_from,
        date_to=period.date_to,
        items=[StatusCountResponse(**vars(item)) for item in items],
    )


@router.get("/top-products", response_model=TopProductsResponse)
async def get_top_products(
    date_from: datetime.date | None = DateFrom,
    date_to: datetime.date | None = DateTo,
    limit: int = Query(default=DEFAULT_TOP_PRODUCTS_LIMIT),
    repository: SQLDashboardRepository = Depends(get_dashboard_repository),
) -> TopProductsResponse:
    period = _period(date_from, date_to)
    items = await GetTopProducts(repository).execute(
        period.date_from, period.date_to, limit
    )
    return TopProductsResponse(
        date_from=period.date_from,
        date_to=period.date_to,
        items=[TopProductResponse(**vars(item)) for item in items],
    )


@router.get("/payment-methods", response_model=PaymentMethodsResponse)
async def get_payment_methods(
    date_from: datetime.date | None = DateFrom,
    date_to: datetime.date | None = DateTo,
    repository: SQLDashboardRepository = Depends(get_dashboard_repository),
) -> PaymentMethodsResponse:
    period = _period(date_from, date_to)
    items = await GetPaymentMethodSplit(repository).execute(
        period.date_from, period.date_to
    )
    return PaymentMethodsResponse(
        date_from=period.date_from,
        date_to=period.date_to,
        items=[PaymentSplitResponse(**vars(item)) for item in items],
    )

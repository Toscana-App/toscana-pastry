from decimal import Decimal

from sqlalchemy import Numeric, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import OrderItemORM, OrderORM
from domain.dashboard import (
    BUSINESS_TZ_NAME,
    MAX_PERIOD_DAYS,
    DashboardPeriod,
    Granularity,
    PaymentSplit,
    SalesPoint,
    SalesTotals,
    StatusCount,
    TopProduct,
    period_bounds,
)
from domain.order import OrderStatus
from domain.repositories import DashboardRepository

_MONEY = Numeric(14, 2)
_ZERO = Decimal("0")
_CANCELLED = OrderStatus.CANCELADO.value
_GROUP_ROW_LIMIT = 50
_TRUNC_UNITS = {
    Granularity.DAY: "'day'",
    Granularity.WEEK: "'week'",
    Granularity.MONTH: "'month'",
}


def _money(column):
    return cast(func.coalesce(func.nullif(column, ""), "0"), _MONEY)


_SNAPSHOT_ROUNDED = r'"rounded"\s*:\s*"(-?[0-9]+(?:\.[0-9]+)?)"'


def _line_total():
    unit_price = cast(func.nullif(OrderItemORM.unit_price, ""), _MONEY)
    snapshot_rounded = cast(
        func.substring(OrderItemORM.snapshot, _SNAPSHOT_ROUNDED), _MONEY
    )
    return func.coalesce(OrderItemORM.quantity * unit_price, snapshot_rounded, 0)


def _order_totals(period: DashboardPeriod):
    start, end = period_bounds(period)
    return (
        select(
            OrderORM.id.label("id"),
            OrderORM.status.label("status"),
            OrderORM.date.label("date"),
            OrderORM.payment_method.label("payment_method"),
            OrderORM.paid_at.label("paid_at"),
            (
                func.coalesce(func.sum(_line_total()), 0)
                - _money(OrderORM.discount_amount)
            ).label("total"),
        )
        .select_from(OrderORM)
        .outerjoin(OrderItemORM, OrderItemORM.order_id == OrderORM.id)
        .where(OrderORM.date >= start, OrderORM.date < end)
        .group_by(OrderORM.id)
        .subquery("order_totals")
    )


class SQLDashboardRepository(DashboardRepository):

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sales_totals(self, period: DashboardPeriod) -> SalesTotals:
        totals = _order_totals(period)
        active = totals.c.status != _CANCELLED
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(totals.c.total).filter(active), 0),
                    func.count().filter(active),
                    func.coalesce(
                        func.sum(totals.c.total).filter(
                            active, totals.c.paid_at.is_not(None)
                        ),
                        0,
                    ),
                    func.count().filter(totals.c.status == _CANCELLED),
                )
            )
        ).one()
        return SalesTotals(
            revenue=Decimal(row[0]),
            orders_count=row[1],
            paid_revenue=Decimal(row[2]),
            cancelled_count=row[3],
        )

    async def sales_series(
        self, period: DashboardPeriod, granularity: Granularity
    ) -> list[SalesPoint]:
        totals = _order_totals(period)
        bucket = func.date_trunc(
            literal_column(_TRUNC_UNITS[granularity]),
            func.timezone(BUSINESS_TZ_NAME, totals.c.date),
        )
        rows = (
            await self.session.execute(
                select(bucket.label("bucket"), func.sum(totals.c.total), func.count())
                .where(totals.c.status != _CANCELLED)
                .group_by(bucket)
                .order_by(bucket)
                .limit(MAX_PERIOD_DAYS + 1)
            )
        ).all()
        return [
            SalesPoint(row[0].date(), Decimal(row[1] or _ZERO), row[2]) for row in rows
        ]

    async def status_counts(self, period: DashboardPeriod) -> list[StatusCount]:
        start, end = period_bounds(period)
        rows = (
            await self.session.execute(
                select(OrderORM.status, func.count())
                .where(OrderORM.date >= start, OrderORM.date < end)
                .group_by(OrderORM.status)
                .limit(_GROUP_ROW_LIMIT)
            )
        ).all()
        return [StatusCount(row[0], row[1]) for row in rows]

    async def top_products(
        self, period: DashboardPeriod, limit: int
    ) -> list[TopProduct]:
        start, end = period_bounds(period)
        revenue = func.sum(_line_total())
        quantity = func.sum(OrderItemORM.quantity)
        rows = (
            await self.session.execute(
                select(
                    OrderItemORM.product_id,
                    OrderItemORM.product_name,
                    quantity,
                    revenue,
                )
                .join(OrderORM, OrderORM.id == OrderItemORM.order_id)
                .where(
                    OrderORM.date >= start,
                    OrderORM.date < end,
                    OrderORM.status != _CANCELLED,
                )
                .group_by(OrderItemORM.product_id, OrderItemORM.product_name)
                .order_by(revenue.desc(), quantity.desc(), OrderItemORM.product_name)
                .limit(limit)
            )
        ).all()
        return [
            TopProduct(row[0], row[1], int(row[2]), Decimal(row[3] or _ZERO))
            for row in rows
        ]

    async def payment_split(self, period: DashboardPeriod) -> list[PaymentSplit]:
        totals = _order_totals(period)
        revenue = func.sum(totals.c.total)
        rows = (
            await self.session.execute(
                select(totals.c.payment_method, func.count(), revenue)
                .where(totals.c.status != _CANCELLED)
                .group_by(totals.c.payment_method)
                .order_by(revenue.desc())
                .limit(_GROUP_ROW_LIMIT)
            )
        ).all()
        return [PaymentSplit(row[0], row[1], Decimal(row[2] or _ZERO)) for row in rows]

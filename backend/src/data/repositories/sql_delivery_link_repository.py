from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import Row, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import OrderDeliveryLinkORM, OrderORM
from domain.delivery import DeliveryLink
from domain.repositories import DeliveryLinkRepository

_LINK_COLUMNS = (
    OrderDeliveryLinkORM.token,
    OrderDeliveryLinkORM.order_id,
    OrderDeliveryLinkORM.created_at,
    OrderDeliveryLinkORM.revoked_at,
    OrderDeliveryLinkORM.revoked_reason,
    OrderORM.code,
    OrderORM.status,
)


def _to_domain(row: Row) -> DeliveryLink:
    return DeliveryLink(
        token=row[0],
        order_id=row[1],
        created_at=row[2],
        revoked_at=row[3],
        revoked_reason=row[4],
        order_code=row[5],
        order_status=row[6],
    )


class SQLDeliveryLinkRepository(DeliveryLinkRepository):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_for_order(self, order_id: str) -> Optional[DeliveryLink]:
        result = await self.session.execute(
            select(*_LINK_COLUMNS)
            .join(OrderORM, OrderORM.id == OrderDeliveryLinkORM.order_id)
            .where(
                OrderDeliveryLinkORM.order_id == order_id,
                OrderDeliveryLinkORM.revoked_at.is_(None),
            )
        )
        row = result.first()
        return _to_domain(row) if row is not None else None

    async def find_by_token(self, token: str) -> Optional[DeliveryLink]:
        result = await self.session.execute(
            select(*_LINK_COLUMNS)
            .join(OrderORM, OrderORM.id == OrderDeliveryLinkORM.order_id)
            .where(OrderDeliveryLinkORM.token == token)
        )
        row = result.first()
        return _to_domain(row) if row is not None else None

    async def create(self, order_id: str, token: str) -> bool:
        try:
            async with self.session.begin_nested():
                self.session.add(
                    OrderDeliveryLinkORM(
                        token=token,
                        order_id=order_id,
                        created_at=datetime.datetime.now(datetime.UTC),
                    )
                )
                await self.session.flush()
        except IntegrityError:
            return False
        await self.session.commit()
        return True

    async def revoke_active(self, order_id: str, reason: str) -> int:
        result = await self.session.execute(
            update(OrderDeliveryLinkORM)
            .where(
                OrderDeliveryLinkORM.order_id == order_id,
                OrderDeliveryLinkORM.revoked_at.is_(None),
            )
            .values(
                revoked_at=datetime.datetime.now(datetime.UTC),
                revoked_reason=reason,
            )
        )
        return int(result.rowcount or 0)

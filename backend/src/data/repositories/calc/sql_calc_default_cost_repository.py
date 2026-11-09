from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CalcDefaultCostORM
from domain.calc_settings import CalcDefaultCost


def _to_domain(orm: CalcDefaultCostORM) -> CalcDefaultCost:
    return CalcDefaultCost(
        id=orm.id,
        name=orm.name,
        type=orm.type,
        default_unit_cost_or_rate=Decimal(orm.default_unit_cost_or_rate),
        default_quantity_or_minutes=Decimal(orm.default_quantity_or_minutes),
        status=orm.status,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_orm(domain: CalcDefaultCost) -> CalcDefaultCostORM:
    return CalcDefaultCostORM(
        id=domain.id,
        name=domain.name,
        type=domain.type,
        default_unit_cost_or_rate=str(domain.default_unit_cost_or_rate),
        default_quantity_or_minutes=str(domain.default_quantity_or_minutes),
        status=domain.status,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


class SQLCalcDefaultCostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        type_filter: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[CalcDefaultCost], int]:
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(func.accent_fold(CalcDefaultCostORM.name).like(f"%{folded}%"))
        if type_filter and type_filter.strip():
            filters.append(CalcDefaultCostORM.type == type_filter.strip())
        count_stmt = select(func.count()).select_from(CalcDefaultCostORM).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            await self.session.execute(
                select(CalcDefaultCostORM)
                .where(*filters)
                .order_by(func.lower(CalcDefaultCostORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows], total

    async def get(self, cost_id: str) -> Optional[CalcDefaultCost]:
        result = await self.session.execute(
            select(CalcDefaultCostORM).where(CalcDefaultCostORM.id == cost_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, cost: CalcDefaultCost) -> CalcDefaultCost:
        self.session.add(_to_orm(cost))
        await self.session.commit()
        return cost

    async def update(self, cost: CalcDefaultCost) -> Optional[CalcDefaultCost]:
        result = await self.session.execute(
            select(CalcDefaultCostORM).where(CalcDefaultCostORM.id == cost.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = cost.name
        orm.type = cost.type
        orm.default_unit_cost_or_rate = str(cost.default_unit_cost_or_rate)
        orm.default_quantity_or_minutes = str(cost.default_quantity_or_minutes)
        orm.status = cost.status
        orm.updated_at = cost.updated_at
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, cost_id: str) -> Optional[CalcDefaultCost]:
        result = await self.session.execute(
            select(CalcDefaultCostORM).where(CalcDefaultCostORM.id == cost_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

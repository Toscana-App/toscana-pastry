"""Repository para CalcProductCategory (RF-P5CC-04).

Mismas reglas que CalcMaterialCategory.
"""
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CalcProductCategoryORM
from domain.calc_settings import CalcProductCategory


def _to_domain(orm: CalcProductCategoryORM) -> CalcProductCategory:
    return CalcProductCategory(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_orm(domain: CalcProductCategory) -> CalcProductCategoryORM:
    return CalcProductCategoryORM(
        id=domain.id,
        name=domain.name,
        description=domain.description,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


class SQLCalcProductCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[CalcProductCategory], int]:
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(func.accent_fold(CalcProductCategoryORM.name).like(f"%{folded}%"))
        count_stmt = select(func.count()).select_from(CalcProductCategoryORM).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            await self.session.execute(
                select(CalcProductCategoryORM)
                .where(*filters)
                .order_by(func.lower(CalcProductCategoryORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows], total

    async def get(self, category_id: str) -> Optional[CalcProductCategory]:
        result = await self.session.execute(
            select(CalcProductCategoryORM).where(CalcProductCategoryORM.id == category_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_by_name(self, name: str) -> Optional[CalcProductCategory]:
        result = await self.session.execute(
            select(CalcProductCategoryORM).where(
                func.lower(CalcProductCategoryORM.name) == name.lower()
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, category: CalcProductCategory) -> CalcProductCategory:
        self.session.add(_to_orm(category))
        await self.session.commit()
        return category

    async def update(self, category: CalcProductCategory) -> Optional[CalcProductCategory]:
        result = await self.session.execute(
            select(CalcProductCategoryORM).where(CalcProductCategoryORM.id == category.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = category.name
        orm.description = category.description
        orm.updated_at = category.updated_at
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, category_id: str) -> Optional[CalcProductCategory]:
        result = await self.session.execute(
            select(CalcProductCategoryORM).where(CalcProductCategoryORM.id == category_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

    async def count_in_use(self, category_id: str) -> int:
        """Stub: productos que referencian esta categoria. B9 lo completa."""
        return 0

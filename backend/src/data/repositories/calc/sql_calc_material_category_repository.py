"""Repository para CalcMaterialCategory (RF-P5CC-03)."""
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CalcMaterialCategoryORM
from domain.calc_settings import CalcMaterialCategory


def _to_domain(orm: CalcMaterialCategoryORM) -> CalcMaterialCategory:
    return CalcMaterialCategory(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _to_orm(domain: CalcMaterialCategory) -> CalcMaterialCategoryORM:
    return CalcMaterialCategoryORM(
        id=domain.id,
        name=domain.name,
        description=domain.description,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


class SQLCalcMaterialCategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[CalcMaterialCategory], int]:
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(func.accent_fold(CalcMaterialCategoryORM.name).like(f"%{folded}%"))
        count_stmt = select(func.count()).select_from(CalcMaterialCategoryORM).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            await self.session.execute(
                select(CalcMaterialCategoryORM)
                .where(*filters)
                .order_by(func.lower(CalcMaterialCategoryORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows], total

    async def get(self, category_id: str) -> Optional[CalcMaterialCategory]:
        result = await self.session.execute(
            select(CalcMaterialCategoryORM).where(CalcMaterialCategoryORM.id == category_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_by_name(self, name: str) -> Optional[CalcMaterialCategory]:
        folded = accent_fold(name) or name
        result = await self.session.execute(
            select(CalcMaterialCategoryORM).where(
                func.accent_fold(CalcMaterialCategoryORM.name) == folded
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, category: CalcMaterialCategory) -> CalcMaterialCategory:
        self.session.add(_to_orm(category))
        await self.session.commit()
        return category

    async def update(self, category: CalcMaterialCategory) -> Optional[CalcMaterialCategory]:
        result = await self.session.execute(
            select(CalcMaterialCategoryORM).where(CalcMaterialCategoryORM.id == category.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = category.name
        orm.description = category.description
        orm.updated_at = category.updated_at
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, category_id: str) -> Optional[CalcMaterialCategory]:
        result = await self.session.execute(
            select(CalcMaterialCategoryORM).where(CalcMaterialCategoryORM.id == category_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

    async def count_in_use(self, category_id: str) -> int:
        """Materiales que referencian esta categoria.

        TODO(B8): completar con consulta real de FK en
        calc_materials.material_category_id cuando B8 agregue la tabla
        calc_materials. Por ahora siempre 0.
        """
        return 0

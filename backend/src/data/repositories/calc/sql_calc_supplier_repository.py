"""Repository para CalcSupplier (RF-P5CC-05)."""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
# El ORM usa el estilo Column legacy (mismo que B1-B10): pyright tipa los
# atributos de instancia como Column[T], no como el valor.
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CalcMaterialORM, CalcSupplierORM
from domain.calc_settings import CalcSupplier


def _to_domain(orm: CalcSupplierORM) -> CalcSupplier:
    return CalcSupplier(  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        name=orm.name,  # type: ignore[arg-type]
        contact_name=orm.contact_name,  # type: ignore[arg-type]
        phone=orm.phone,  # type: ignore[arg-type]
        email=orm.email,  # type: ignore[arg-type]
        notes=orm.notes,  # type: ignore[arg-type]
        created_at=orm.created_at,  # type: ignore[arg-type]
        updated_at=orm.updated_at,  # type: ignore[arg-type]
    )


def _to_orm(domain: CalcSupplier) -> CalcSupplierORM:
    return CalcSupplierORM(
        id=domain.id,
        name=domain.name,
        contact_name=domain.contact_name,
        phone=domain.phone,
        email=domain.email,
        notes=domain.notes,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )


class SQLCalcSupplierRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CalcSupplier], int]:
        filters = []
        if q and q.strip():
            folded = accent_fold(q) or q
            filters.append(func.accent_fold(CalcSupplierORM.name).like(f"%{folded}%"))
        count_stmt = select(func.count()).select_from(CalcSupplierORM).where(*filters)
        total = (await self.session.execute(count_stmt)).scalar_one()
        rows = (
            await self.session.execute(
                select(CalcSupplierORM)
                .where(*filters)
                .order_by(func.lower(CalcSupplierORM.name))
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows], total

    async def get(self, supplier_id: str) -> CalcSupplier | None:
        result = await self.session.execute(
            select(CalcSupplierORM).where(CalcSupplierORM.id == supplier_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_by_name(self, name: str) -> CalcSupplier | None:
        folded = accent_fold(name) or name
        result = await self.session.execute(
            select(CalcSupplierORM).where(
                func.accent_fold(CalcSupplierORM.name) == folded
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def create(self, supplier: CalcSupplier) -> CalcSupplier:
        self.session.add(_to_orm(supplier))
        await self.session.commit()
        return supplier

    async def update(self, supplier: CalcSupplier) -> CalcSupplier | None:
        result = await self.session.execute(
            select(CalcSupplierORM).where(CalcSupplierORM.id == supplier.id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.name = supplier.name
        orm.contact_name = supplier.contact_name
        orm.phone = supplier.phone
        orm.email = supplier.email
        orm.notes = supplier.notes
        orm.updated_at = supplier.updated_at
        await self.session.commit()
        return _to_domain(orm)

    async def delete(self, supplier_id: str) -> CalcSupplier | None:
        result = await self.session.execute(
            select(CalcSupplierORM).where(CalcSupplierORM.id == supplier_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        await self.session.delete(orm)
        await self.session.commit()
        return _to_domain(orm)

    async def count_in_use(self, supplier_id: str) -> int:
        """Materiales que referencian este proveedor (FK real en
        calc_materials.supplier_id, B8)."""
        stmt = select(func.count()).select_from(CalcMaterialORM).where(
            CalcMaterialORM.supplier_id == supplier_id
        )
        return (await self.session.execute(stmt)).scalar_one()

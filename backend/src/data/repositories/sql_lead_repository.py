"""Repository de leads (RF-P11-13, C5).

Mapeo ORM↔dominio y operaciones de gestion admin.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import LeadORM
from domain.lead import Lead


def _to_domain(orm: LeadORM) -> Lead:
    return Lead(
        id=orm.id,
        name=orm.name,
        email=orm.email,
        customer_type=orm.customer_type,  # type: ignore[arg-type]
        message=orm.message,
        phone=orm.phone,
        business_name=orm.business_name,
        location=orm.location,
        read=orm.read,
    )


def _to_orm(domain: Lead) -> LeadORM:
    return LeadORM(
        id=domain.id,
        name=domain.name,
        email=domain.email,
        customer_type=domain.customer_type,
        message=domain.message,
        phone=domain.phone,
        business_name=domain.business_name,
        location=domain.location,
        read=domain.read,
    )


class SQLLeadRepository:
    """SQL repository for Lead entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, lead: Lead) -> Lead:
        self.session.add(_to_orm(lead))
        await self.session.commit()
        return lead

    async def list(
        self,
        q: str | None,
        read: bool | None,
        customer_type: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Lead], int]:
        """Listado admin: ?q en name/email, ?read, ?customer_type."""
        filters = []
        if q and q.strip():
            q_lower = q.lower()
            filters.append(
                func.lower(LeadORM.name).like(f"%{q_lower}%")
                | func.lower(LeadORM.email).like(f"%{q_lower}%")
            )
        if read is not None:
            filters.append(LeadORM.read == read)
        if customer_type:
            filters.append(LeadORM.customer_type == customer_type)

        count_stmt = (
            select(func.count()).select_from(LeadORM).where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        rows = (
            await self.session.execute(
                select(LeadORM)
                .where(*filters)
                .order_by(LeadORM.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return [_to_domain(r) for r in rows], total

    async def get(self, lead_id: str) -> Lead | None:
        result = await self.session.execute(
            select(LeadORM).where(LeadORM.id == lead_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def set_read(self, lead_id: str, read: bool) -> Lead | None:
        """Marca un lead como leido/no-leido."""
        result = await self.session.execute(
            select(LeadORM).where(LeadORM.id == lead_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        orm.read = read
        await self.session.commit()
        return _to_domain(orm)

    async def mark_all_read(self) -> int:
        """Marca todos los leads como leidos. Retorna cantidad actualizada."""
        result = await self.session.execute(
            select(LeadORM).where(LeadORM.read == False)  # noqa: E712
        )
        rows = result.scalars().all()
        count = len(rows)
        for row in rows:
            row.read = True
        await self.session.commit()
        return count

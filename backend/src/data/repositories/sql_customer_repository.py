from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from data.accent import accent_fold
from data.models import CustomerORM
from domain.orders import Customer


def _to_domain(orm: CustomerORM) -> Customer:
    return Customer(  # type: ignore[arg-type]
        name=orm.name,  # type: ignore[arg-type]
        phone=orm.phone,  # type: ignore[arg-type]
        id=orm.id,  # type: ignore[arg-type]
        delivery_address=orm.delivery_address,  # type: ignore[arg-type]
        created_at=orm.created_at,  # type: ignore[arg-type]
    )


class SQLCustomerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[Customer], int]:
        filters = []
        if q and q.strip():
            # Nombre: plegado de acentos (RF-P2-02). Telefono: subcadena de
            # digitos (busscar "155" encuentra "11 2345 6789").
            folded = accent_fold(q) or q
            filters.append(
                or_(
                    func.accent_fold(CustomerORM.name).like(f"%{folded}%"),
                    CustomerORM.phone_norm.like(f"%{folded.replace(' ', '')}%"),
                )
            )
        total = (
            await self.session.execute(
                select(func.count()).select_from(CustomerORM).where(*filters)
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(CustomerORM)
                .where(*filters)
                .order_by(func.lower(CustomerORM.name), CustomerORM.created_at)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return [_to_domain(orm) for orm in rows], total

    async def get(self, customer_id: str) -> Optional[Customer]:
        result = await self.session.execute(
            select(CustomerORM).where(CustomerORM.id == customer_id)
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def get_or_create(
        self, customer: Customer
    ) -> Tuple[Customer, bool]:
        """Dedup por (name_norm, phone_norm) (RF-P6-08). En carrera el
        constraint unico protege: el perdedor relee al ganador."""
        existing = await self._find_by_norm(customer.name_norm, customer.phone_norm)
        if existing is not None:
            return existing, False
        orm = CustomerORM(
            id=customer.id,
            name=customer.name,
            phone=customer.phone,
            name_norm=customer.name_norm,
            phone_norm=customer.phone_norm,
            delivery_address=customer.delivery_address,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(orm)
        await self.session.commit()
        await self.session.refresh(orm)
        return customer, True

    async def _find_by_norm(
        self, name_norm: str, phone_norm: str
    ) -> Optional[Customer]:
        result = await self.session.execute(
            select(CustomerORM).where(
                CustomerORM.name_norm == name_norm,
                CustomerORM.phone_norm == phone_norm,
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def update_address(
        self, customer_id: str, delivery_address: Optional[str]
    ) -> Optional[Customer]:
        """Actualiza la direccion de entrega (RF-P7-06). Cadena vacia o
        None limpia el valor. None de retorno = cliente inexistente."""
        result = await self.session.execute(
            select(CustomerORM).where(CustomerORM.id == customer_id)
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        stripped = (delivery_address or "").strip() or None
        if stripped is not None and len(stripped) > 500:
            raise ValueError(
                "La direccion de entrega no puede superar 500 caracteres"
            )
        orm.delivery_address = stripped
        await self.session.commit()
        await self.session.refresh(orm)
        return _to_domain(orm)

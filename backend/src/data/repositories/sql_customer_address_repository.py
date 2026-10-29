"""Repository para CustomerAddress (RF-P11-09, C2).

Las operaciones mutan con flush (sin commit) para que el router pueda
encadenar varios pasos (ej. demover la default anterior + marcar la nueva)
y cerrar con un unico commit atomico por request.
"""
import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import CustomerAddressORM
from domain.customer_address import CustomerAddress


def _to_domain(orm: CustomerAddressORM) -> CustomerAddress:
    return CustomerAddress(
        street_line_1=orm.street_line_1,
        street_line_2=orm.street_line_2,
        city=orm.city,
        postal_code=orm.postal_code,
        province=orm.province,
        phone=orm.phone,
        is_default=orm.is_default,
        id=orm.id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SQLCustomerAddressRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(self, user_id: str) -> List[CustomerAddress]:
        """Todas las direcciones del usuario, de la mas antigua a la mas nueva."""
        rows = (
            await self.session.execute(
                select(CustomerAddressORM)
                .where(CustomerAddressORM.user_id == user_id)
                .order_by(CustomerAddressORM.created_at)
            )
        ).scalars().all()
        return [_to_domain(r) for r in rows]

    async def get_for_user(
        self, address_id: str, user_id: str
    ) -> Optional[CustomerAddress]:
        """Direccion por id SOLO si pertenece al usuario (anti-sondeo:
        direcciones ajenas se indistinguibles de inexistentes -> None)."""
        result = await self.session.execute(
            select(CustomerAddressORM).where(
                CustomerAddressORM.id == address_id,
                CustomerAddressORM.user_id == user_id,
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def count_by_user(self, user_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(CustomerAddressORM)
                .where(CustomerAddressORM.user_id == user_id)
            )
        ).scalar_one()

    async def default_for_user(self, user_id: str) -> Optional[CustomerAddress]:
        result = await self.session.execute(
            select(CustomerAddressORM).where(
                CustomerAddressORM.user_id == user_id,
                CustomerAddressORM.is_default.is_(True),
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def insert(self, address: CustomerAddress, user_id: str) -> None:
        self.session.add(
            CustomerAddressORM(
                id=address.id,
                user_id=user_id,
                street_line_1=address.street_line_1,
                street_line_2=address.street_line_2,
                city=address.city,
                postal_code=address.postal_code,
                province=address.province,
                phone=address.phone,
                is_default=address.is_default,
                created_at=address.created_at,
                updated_at=address.updated_at,
            )
        )
        await self.session.flush()

    async def set_fields(
        self, address: CustomerAddress, user_id: str
    ) -> None:
        """Aplica todos los campos de `address` a la fila del usuario."""
        result = await self.session.execute(
            select(CustomerAddressORM).where(
                CustomerAddressORM.id == address.id,
                CustomerAddressORM.user_id == user_id,
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return
        orm.street_line_1 = address.street_line_1
        orm.street_line_2 = address.street_line_2
        orm.city = address.city
        orm.postal_code = address.postal_code
        orm.province = address.province
        orm.phone = address.phone
        orm.is_default = address.is_default
        orm.updated_at = datetime.datetime.now(datetime.UTC)
        await self.session.flush()

    async def set_default_flag(
        self, address_id: str, user_id: str, is_default: bool
    ) -> None:
        """Cambia solo el flag is_default (para demover/promover la default)."""
        result = await self.session.execute(
            update(CustomerAddressORM)
            .where(
                CustomerAddressORM.id == address_id,
                CustomerAddressORM.user_id == user_id,
            )
            .values(
                is_default=is_default,
                updated_at=datetime.datetime.now(datetime.UTC),
            )
        )
        if result.rowcount == 0:
            return
        await self.session.flush()

    async def remove(self, address_id: str, user_id: str) -> Optional[CustomerAddress]:
        result = await self.session.execute(
            select(CustomerAddressORM).where(
                CustomerAddressORM.id == address_id,
                CustomerAddressORM.user_id == user_id,
            )
        )
        orm = result.scalars().first()
        if orm is None:
            return None
        domain = _to_domain(orm)
        await self.session.execute(
            delete(CustomerAddressORM).where(CustomerAddressORM.id == address_id)
        )
        await self.session.flush()
        return domain

    async def commit(self) -> None:
        await self.session.commit()

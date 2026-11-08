import datetime
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import CustomerAddressORM, UserORM
from domain.customer_address import CustomerAddress
from domain.repositories import CustomerAddressRepository


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


class SQLCustomerAddressRepository(CustomerAddressRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(self, user_id: str) -> List[CustomerAddress]:
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
        result = await self.session.execute(
            select(CustomerAddressORM).where(
                CustomerAddressORM.id == address_id,
                CustomerAddressORM.user_id == user_id,
            )
        )
        orm = result.scalars().first()
        return _to_domain(orm) if orm else None

    async def lock_book(self, user_id: str) -> None:
        await self.session.execute(
            select(UserORM.id).where(UserORM.id == user_id).with_for_update()
        )

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

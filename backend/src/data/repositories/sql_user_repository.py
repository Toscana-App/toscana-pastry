from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import User, UserRole
from data.models import UserORM

def _to_domain(orm_user: UserORM) -> User:
    # Normalize legacy uppercase values (SQLAlchemyEnum persisted names before
    # the values_callable fix) so that rows edited by hand or from old backups
    # don't explode with LookupError → 500.
    raw_role = orm_user.role
    if isinstance(raw_role, str):
        raw_role = raw_role.lower()
    return User(
        id=orm_user.id,
        email=orm_user.email,
        role=UserRole(raw_role),
        google_id=orm_user.google_id,
    )

class SQLUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.email == email))
        orm_user = result.scalars().first()
        return _to_domain(orm_user) if orm_user else None

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.google_id == google_id))
        orm_user = result.scalars().first()
        return _to_domain(orm_user) if orm_user else None

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id))
        orm_user = result.scalars().first()
        return _to_domain(orm_user) if orm_user else None

    async def save(self, user: User) -> User:
        user_orm = UserORM(
            id=str(user.id),
            email=user.email,
            role=user.role,
            google_id=user.google_id,
        )
        self.session.add(user_orm)
        await self.session.commit()
        return user

    async def get_all_by_role(self, role: UserRole) -> List[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.role == role))
        return [_to_domain(u) for u in result.scalars().all()]

    async def get_all(self) -> List[User]:
        result = await self.session.execute(select(UserORM))
        return [_to_domain(u) for u in result.scalars().all()]

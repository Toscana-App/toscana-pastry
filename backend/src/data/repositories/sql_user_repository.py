from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import User
from data.models import UserORM

class SQLUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.email == email))
        orm_user = result.scalars().first()
        if not orm_user:
            return None
        return User(
            id=orm_user.id,
            email=orm_user.email,
            google_id=orm_user.google_id,
            created_at=orm_user.created_at
        )

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.google_id == google_id))
        orm_user = result.scalars().first()
        if not orm_user:
            return None
        return User(
            id=orm_user.id,
            email=orm_user.email,
            google_id=orm_user.google_id,
            created_at=orm_user.created_at
        )

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id))
        orm_user = result.scalars().first()
        if not orm_user:
            return None
        return User(
            id=orm_user.id,
            email=orm_user.email,
            google_id=orm_user.google_id,
            created_at=orm_user.created_at
        )

    async def save(self, user: User) -> User:
        user_orm = UserORM(
            id=str(user.id),
            email=user.email,
            google_id=user.google_id,
            created_at=user.created_at
        )
        self.session.add(user_orm)
        await self.session.commit()
        return user

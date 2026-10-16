from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from domain.models import User, UserRole
from data.models import UserORM, UserRoleEnum

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
            role=UserRole(orm_user.role),
            google_id=orm_user.google_id,
        )

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.google_id == google_id))
        orm_user = result.scalars().first()
        if not orm_user:
            return None
        return User(
            id=orm_user.id,
            email=orm_user.email,
            role=UserRole(orm_user.role),
            google_id=orm_user.google_id,
        )

    async def get_by_id(self, user_id: str) -> Optional[User]:
        result = await self.session.execute(select(UserORM).where(UserORM.id == user_id))
        orm_user = result.scalars().first()
        if not orm_user:
            return None
        return User(
            id=orm_user.id,
            email=orm_user.email,
            role=UserRole(orm_user.role),
            google_id=orm_user.google_id,
        )

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
        result = await self.session.execute(select(UserORM).where(UserORM.role == role.value))
        orm_users = result.scalars().all()
        return [
            User(
                id=u.id,
                email=u.email,
                role=UserRole(u.role),
                google_id=u.google_id,
            )
            for u in orm_users
        ]

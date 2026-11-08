from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from domain.repositories import RefreshTokenRepository, UserRepository
from data.repositories.sql_refresh_token_repository import SQLRefreshTokenRepository
from data.repositories.sql_user_repository import SQLUserRepository
from data.db import get_db

async def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    yield SQLUserRepository(db)


async def get_refresh_token_repository(
    db: AsyncSession = Depends(get_db),
) -> RefreshTokenRepository:
    yield SQLRefreshTokenRepository(db)

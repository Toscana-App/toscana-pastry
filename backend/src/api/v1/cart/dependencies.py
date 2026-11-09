from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_cart_repository import SQLCartRepository


def get_cart_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCartRepository:
    return SQLCartRepository(db)

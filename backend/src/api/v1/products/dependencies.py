from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_product_repository import SQLProductRepository


def get_product_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLProductRepository:
    return SQLProductRepository(db)

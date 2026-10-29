"""Order API dependencies (C1)."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_order_repository import SQLOrderRepository


def get_order_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLOrderRepository:
    return SQLOrderRepository(db)

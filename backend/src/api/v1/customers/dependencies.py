from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_customer_repository import SQLCustomerRepository


def get_customer_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerRepository:
    return SQLCustomerRepository(db)

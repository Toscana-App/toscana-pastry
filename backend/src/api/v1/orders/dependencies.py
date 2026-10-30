"""Order API dependencies (P6)."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_customer_repository import SQLCustomerRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_product_repository import SQLProductRepository


def get_order_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLOrderRepository:
    return SQLOrderRepository(db)


def get_customer_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerRepository:
    return SQLCustomerRepository(db)


def get_product_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLProductRepository:
    return SQLProductRepository(db)

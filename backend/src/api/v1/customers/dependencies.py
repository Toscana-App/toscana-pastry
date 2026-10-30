"""Dependencies para el libro de direcciones de clientes (RF-P11-09)."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_customer_address_repository import (
    SQLCustomerAddressRepository,
)
from data.repositories.sql_customer_repository import SQLCustomerRepository


def get_customer_address_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerAddressRepository:
    return SQLCustomerAddressRepository(db)


def get_customer_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerRepository:
    return SQLCustomerRepository(db)

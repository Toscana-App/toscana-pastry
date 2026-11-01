"""Dependencies de clientes: repositorio P6 y libro de direcciones (RF-P11-09)."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_customer_address_repository import (
    SQLCustomerAddressRepository,
)
from data.repositories.sql_customer_repository import SQLCustomerRepository
from domain.repositories import CustomerAddressRepository


def get_customer_address_repository(
    db: AsyncSession = Depends(get_db),
) -> CustomerAddressRepository:
    return SQLCustomerAddressRepository(db)


def get_customer_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerRepository:
    return SQLCustomerRepository(db)

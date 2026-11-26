from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_delivery_link_repository import SQLDeliveryLinkRepository


def get_delivery_link_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLDeliveryLinkRepository:
    return SQLDeliveryLinkRepository(db)

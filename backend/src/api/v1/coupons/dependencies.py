from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_coupon_repository import SQLCouponRepository


def get_coupon_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCouponRepository:
    return SQLCouponRepository(db)

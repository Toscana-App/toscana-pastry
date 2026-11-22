from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_dashboard_repository import SQLDashboardRepository


def get_dashboard_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLDashboardRepository:
    return SQLDashboardRepository(db)

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_budget_repository import SQLBudgetRepository


def get_budget_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLBudgetRepository:
    return SQLBudgetRepository(db)

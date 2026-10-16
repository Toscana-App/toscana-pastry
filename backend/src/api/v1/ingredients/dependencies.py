from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_ingredient_repository import SQLIngredientRepository


def get_ingredient_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLIngredientRepository:
    return SQLIngredientRepository(db)

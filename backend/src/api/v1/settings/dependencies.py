from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_settings_repository import SQLSettingsRepository


def get_settings_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLSettingsRepository:
    return SQLSettingsRepository(db)

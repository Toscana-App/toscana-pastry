from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.sql_document_repository import SQLDocumentRepository


def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLDocumentRepository:
    return SQLDocumentRepository(db)

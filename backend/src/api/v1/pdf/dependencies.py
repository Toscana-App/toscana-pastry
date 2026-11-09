from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.pdf.client import PdfClient
from data.repositories.sql_document_repository import SQLDocumentRepository
from core.config import settings as app_settings


def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLDocumentRepository:
    return SQLDocumentRepository(db)


def get_pdf_client() -> PdfClient:
    return PdfClient(app_settings.PDFGEN_URL)

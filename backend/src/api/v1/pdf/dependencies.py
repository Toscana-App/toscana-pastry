from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.pdf.reportlab_renderer import ReportLabPdfRenderer
from data.repositories.sql_document_repository import SQLDocumentRepository
from domain.pdf import PdfRenderer


def get_document_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLDocumentRepository:
    return SQLDocumentRepository(db)


def get_pdf_renderer() -> PdfRenderer:
    return ReportLabPdfRenderer()

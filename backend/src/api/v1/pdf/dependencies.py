"""DI de los dependidos del router de PDF (Fase 8, P9).

El render vive en el binario independiente ``pdfgenerator`` (ADR-0001);
aquí se inyecta el cliente HTTP que lo consume. El test sobreescribe
``get_pdf_client`` para no depender del servicio en la suite.
"""
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

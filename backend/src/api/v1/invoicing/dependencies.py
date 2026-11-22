from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings as app_settings
from data.db import get_db
from data.invoicing.wsfe import build_afip_client
from data.pdf.client import PdfClient
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.invoicing import AfipClient
from domain.pdf import InvoicePdfRenderer


def get_invoice_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLInvoiceRepository:
    return SQLInvoiceRepository(db)


def get_invoicing_order_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLOrderRepository:
    return SQLOrderRepository(db)


def get_afip_client() -> AfipClient:
    return build_afip_client()


def get_invoice_pdf_renderer() -> InvoicePdfRenderer:
    return PdfClient(app_settings.PDFGEN_URL)

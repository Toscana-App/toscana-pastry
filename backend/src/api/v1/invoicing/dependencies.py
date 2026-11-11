from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.invoicing.wsfe import build_afip_client
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.invoicing import AfipClient


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

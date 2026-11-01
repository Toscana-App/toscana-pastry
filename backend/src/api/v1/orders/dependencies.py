"""Order API dependencies (P6)."""

import datetime

from fastapi import Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from data.db import get_db
from data.repositories.sql_customer_repository import SQLCustomerRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.payments.mercadopago import MercadoPagoCheckoutProvider
from domain.checkout_provider import CheckoutProvider


def get_order_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLOrderRepository:
    return SQLOrderRepository(db)


def get_customer_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCustomerRepository:
    return SQLCustomerRepository(db)


def get_product_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLProductRepository:
    return SQLProductRepository(db)


def get_checkout_provider() -> CheckoutProvider:
    """Mercado Pago Checkout Pro provider; 503 when it is not configured."""
    if not settings.MP_ACCESS_TOKEN or not settings.MP_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="payment_provider_unavailable",
        )
    return MercadoPagoCheckoutProvider(
        access_token=settings.MP_ACCESS_TOKEN,
        webhook_secret=settings.MP_WEBHOOK_SECRET,
        notification_url=settings.MP_NOTIFICATION_URL or None,
        back_url=settings.MP_BACK_URL or None,
    )


def get_now() -> datetime.datetime:
    """Current UTC time; overridable in tests (no sleeps)."""
    return datetime.datetime.now(datetime.UTC)

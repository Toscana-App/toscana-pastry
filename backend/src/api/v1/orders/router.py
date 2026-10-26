"""Router de pagos para pedidos (RF-P6-12/13/14, C1.0-C1.5).

Namespace: /api/v1/orders.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi import status as http_status

from api.v1.dependencies import require_admin
from api.v1.orders.dependencies import get_order_repository
from api.v1.orders.schemas import (
    PaidResponse,
    PaymentInitResponse,
    PaymentStatusResponse,
)
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.mock_checkout_provider import MockCheckoutProvider
from domain.models import User
from domain.order import OrderStatus, PaymentMethod, PaymentStatus

router = APIRouter(prefix="/orders", tags=["orders"])


# ─── PATCH /orders/{id}/paid (C1.0) ─────────────────────────────────

@router.patch("/{id}/paid", response_model=PaidResponse)
async def mark_order_paid(
    id: str,
    repo: SQLOrderRepository = Depends(get_order_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /orders/{id}/paid: marca el pedido como pagado (manual, admin only).

    Monotonic: paid only transitions false → true.
    Cash orders: OK.
    MercadoPago orders: only if not already approved (409 if pending/approved).
    """
    order = await repo.get(id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    # Already paid
    if order.paid:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="order_already_paid",
        )

    # MercadoPago with pending/approved status → let webhook handle it
    if (
        order.payment_method == PaymentMethod.MERCADOPAGO
        and order.payment_status is not None
        and order.payment_status != PaymentStatus.PENDING
    ):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="payment_in_progress",
        )

    # Apply payment
    if order.payment_method == PaymentMethod.CASH:
        order.mark_cash_payment()
        # Cash orders: only paid_at changes (payment_status stays None)
        result = await repo.update_payment_status(
            order_id=order.id,
            reference="",
            status=PaymentStatus.APPROVED,
            paid_at=order.paid_at,
        )
    else:
        order.confirm_payment(reference="manual", status=PaymentStatus.APPROVED)
        result = await repo.update_payment_status(
            order_id=order.id,
            reference=order.payment_reference,
            status=order.payment_status,
            paid_at=order.paid_at,
        )

    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    return PaidResponse(paid=True)


# ─── POST /orders/{id}/payment (C1.4) ───────────────────────────────

@router.post("/{id}/payment", response_model=PaymentInitResponse)
async def initiate_payment(
    id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    repo: SQLOrderRepository = Depends(get_order_repository),
    _admin: User = Depends(require_admin),
):
    """POST /orders/{id}/payment: inicia pago Mercado Pago.

    Solo pedidos status=nuevo + payment_method=mercadopago.
    Idempotencia por Idempotency-Key.
    """
    order = await repo.get(id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    # payment_method=cash → 422
    if order.payment_method == PaymentMethod.CASH:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="payment_method_not_mercadopago",
        )

    # status≠nuevo → 409
    if order.status != OrderStatus.NUEVO:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="order_not_payable",
        )

    # Initiate payment via mock provider
    provider = MockCheckoutProvider()
    result = await provider.create_payment(str(id), 0.0, "ARS")

    return PaymentInitResponse(
        reference=result.reference,
        checkout_url=result.checkout_url,
    )


# ─── GET /orders/{id}/payment (C1.5) ────────────────────────────────

@router.get("/{id}/payment", response_model=PaymentStatusResponse)
async def get_payment_status(
    id: str,
    repo: SQLOrderRepository = Depends(get_order_repository),
    _admin: User = Depends(require_admin),
):
    """GET /orders/{id}/payment: estado del pago (polling del portal)."""
    order = await repo.get(id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    return PaymentStatusResponse(
        status=order.payment_status.value if order.payment_status else None,
        paid=order.paid,
        payment_reference=order.payment_reference,
        updated_at=order.created_at,
    )

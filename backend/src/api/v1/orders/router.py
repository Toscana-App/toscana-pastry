"""Router de pagos para pedidos (RF-P6-12/13/14, C1.0-C1.5 / RF-P11-06/08, C6).

Namespace: /api/v1/orders.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi import status as http_status

from api.v1.dependencies import require_admin, get_current_user
from api.v1.orders.dependencies import get_checkout_provider, get_order_repository
from api.v1.orders.schemas import (
    OrderDetailSchema,
    OrderItemSchema,
    OrderListSchema,
    PaidResponse,
    PaymentInitResponse,
    PaymentStatusResponse,
    PortalOrderCreateRequest,
)
from data.models import OrderItemORM, OrderORM
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.checkout_provider import CheckoutProvider, PaymentProviderError
from domain.models import User, UserRole
from domain.order import DeliveryMode, Order, OrderStatus, PaymentMethod, PaymentStatus

router = APIRouter(prefix="/orders", tags=["orders"])

# Mercado Pago app is MLA (Argentina): orders are charged in ARS.
_PAYMENT_CURRENCY = "ARS"


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


_FINAL_PAYMENT_STATUSES = (
    PaymentStatus.APPROVED,
    PaymentStatus.REJECTED,
    PaymentStatus.FAILED,
)


async def _get_own_order(repo: SQLOrderRepository, order_id: str, user: User) -> Order:
    """Order visible to ``user`` (owner or admin); 404 otherwise (anti-probing)."""
    order = await repo.get(order_id)
    if order is None or (user.role != UserRole.ADMIN and order.customer_id != user.id):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return order


# ─── POST /orders/{id}/payment (C1.4) ───────────────────────────────

@router.post("/{id}/payment", response_model=PaymentInitResponse)
async def initiate_payment(
    id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    repo: SQLOrderRepository = Depends(get_order_repository),
    user: User = Depends(get_current_user),
    provider: CheckoutProvider = Depends(get_checkout_provider),
):
    """POST /orders/{id}/payment: inicia pago Mercado Pago (Checkout Pro).

    Dueño del pedido o admin. Solo pedidos status=nuevo +
    payment_method=mercadopago. Idempotencia por Idempotency-Key.
    """
    order = await _get_own_order(repo, id, user)

    # Same key → same saved response.
    saved = await repo.get_payment_attempt(order.id, idempotency_key)
    if saved is not None:
        return PaymentInitResponse(
            reference=saved.reference, checkout_url=saved.checkout_url
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

    if order.paid or order.payment_status in _FINAL_PAYMENT_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="payment_finalized",
        )
    if order.payment_status == PaymentStatus.PENDING:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="payment_in_progress",
        )

    amount = order.total - (order.discount_amount or Decimal("0"))
    try:
        result = await provider.create_payment(order.id, float(amount), _PAYMENT_CURRENCY)
    except PaymentProviderError as err:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="payment_provider_error",
        ) from err

    result = await repo.save_payment_attempt(order.id, idempotency_key, result)
    return PaymentInitResponse(
        reference=result.reference,
        checkout_url=result.checkout_url,
    )


# ─── GET /orders/{id}/payment (C1.5) ────────────────────────────────

@router.get("/{id}/payment", response_model=PaymentStatusResponse)
async def get_payment_status(
    id: str,
    repo: SQLOrderRepository = Depends(get_order_repository),
    user: User = Depends(get_current_user),
):
    """GET /orders/{id}/payment: estado del pago (polling del portal).

    Dueño del pedido o admin; pedidos ajenos → 404.
    """
    order = await _get_own_order(repo, id, user)

    return PaymentStatusResponse(
        status=order.payment_status.value if order.payment_status else None,
        paid=order.paid,
        payment_reference=order.payment_reference,
        updated_at=order.created_at,
    )


# ─── C6 Portal endpoints: POST /orders, GET /orders/mine ────────────

@router.post("/", response_model=OrderDetailSchema)
async def create_order_portal(
    body: PortalOrderCreateRequest,
    user: User = Depends(get_current_user),
    repo: SQLOrderRepository = Depends(get_order_repository),
):
    """POST /orders: crea un pedido desde el portal (C6, RF-P11-06/08).

    Checks:
        - order_window.open → 409 if closed
        - delivery_mode=delivery requires non-empty delivery_address → 422
        - date >= today
        - payment_method ∈ {mercadopago, cash}
    """
    # Check order window
    window = await repo.get_order_window()
    if not window.open:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="order_window_closed",
            headers={"Reafter": str(window.reopens_at) if window.reopens_at else ""},
        )

    # Validate delivery address
    if body.delivery_mode == "delivery" and (
        not body.delivery_address or not body.delivery_address.strip()
    ):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="delivery_requires_address",
        )

    # Validate date (must be >= today)
    import datetime as dt
    today = dt.datetime.now(dt.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    order_date = body.date.replace(tzinfo=None) if body.date.tzinfo else body.date
    if order_date < today:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_must_be_today_or_later",
        )

    # Validate payment_method
    try:
        payment_method = PaymentMethod(body.payment_method)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_payment_method",
        )

    # Build items
    items = []
    for item_data in body.items:
        items.append(
            OrderItemORM(
                id=str(__import__("uuid").uuid4()),
                order_id="",  # placeholder, set after flush
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                quantity=item_data["quantity"],
                unit_price=str(item_data["unit_price"]),
                portion_note=item_data.get("portion_note", ""),
            )
        )

    # Build delivery_mode
    try:
        delivery_mode = DeliveryMode(body.delivery_mode)
    except ValueError:
        delivery_mode = DeliveryMode.DELIVERY

    import uuid as uuid_mod
    order_id = str(uuid_mod.uuid4())
    order_code = f"TP{uuid_mod.uuid4().hex[:6].upper()}"
    created_at = dt.datetime.now(dt.UTC)

    # Persist order + items
    orm = OrderORM(
        id=order_id,
        customer_id=user.id,
        code=order_code,
        date=body.date.replace(tzinfo=None) if body.date.tzinfo else body.date,
        status="nuevo",
        payment_method=payment_method.value,
        delivery_mode=delivery_mode.value,
        delivery_address=body.delivery_address or "",
        coupon_code=body.coupon_code,
        discount_amount=None,
        created_at=created_at,
    )
    repo.session.add(orm)
    await repo.session.flush()

    # Add items with correct order_id
    for item_orm in items:
        item_orm.order_id = orm.id
        item_orm.id = str(__import__("uuid").uuid4())
        repo.session.add(item_orm)
    await repo.session.commit()

    # Fetch back and return
    result = await repo.get(order_id)
    if result is None:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="order_creation_failed",
        )

    return OrderDetailSchema(
        id=result.id,
        code=result.code,
        customer_id=result.customer_id,
        status=result.status.value,
        date=result.date,
        payment_method=result.payment_method.value,
        delivery_mode=result.delivery_mode if isinstance(result.delivery_mode, str) else result.delivery_mode.value,
        delivery_address=result.delivery_address or None,
        coupon_code=result.coupon_code,
        discount_amount=result.discount_amount,
        paid=result.paid,
        payment_status=result.payment_status.value if result.payment_status else None,
        total=result.total,
        items=[
            OrderItemSchema(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                portion_note=item.portion_note,
                total=item.total,
            )
            for item in result.items
        ],
        created_at=result.created_at,
    )


@router.get("/mine", response_model=OrderListSchema)
async def list_my_orders(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    repo: SQLOrderRepository = Depends(get_order_repository),
):
    """GET /orders/mine: lista de pedidos del usuario (RF-P11-08)."""
    orders, total = await repo.list_by_customer(
        user.id, page=page, page_size=page_size
    )
    return OrderListSchema(
        orders=[
            OrderDetailSchema(
                id=o.id,
                code=o.code,
                customer_id=o.customer_id,
                status=o.status.value,
                date=o.date,
                payment_method=o.payment_method.value,
                delivery_mode=o.delivery_mode if isinstance(o.delivery_mode, str) else o.delivery_mode.value,
                delivery_address=o.delivery_address or None,
                coupon_code=o.coupon_code,
                discount_amount=o.discount_amount,
                paid=o.paid,
                payment_status=o.payment_status.value if o.payment_status else None,
                total=o.total,
                items=[
                    OrderItemSchema(
                        product_id=item.product_id,
                        product_name=item.product_name,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        portion_note=item.portion_note,
                        total=item.total,
                    )
                    for item in o.items
                ],
                created_at=o.created_at,
            )
            for o in orders
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/mine/{code}", response_model=OrderDetailSchema)
async def get_my_order(
    code: str,
    user: User = Depends(get_current_user),
    repo: SQLOrderRepository = Depends(get_order_repository),
):
    """GET /orders/mine/{code}: detalle de un pedido por su código (RF-P11-08).

    Anti-spoofing: 404 if the order does not belong to the user.
    """
    order = await repo.get_by_code(code)
    if order is None or order.customer_id != user.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return OrderDetailSchema(
        id=order.id,
        code=order.code,
        customer_id=order.customer_id,
        status=order.status.value,
        date=order.date,
        payment_method=order.payment_method.value,
        delivery_mode=order.delivery_mode if isinstance(order.delivery_mode, str) else order.delivery_mode.value,
        delivery_address=order.delivery_address or None,
        coupon_code=order.coupon_code,
        discount_amount=order.discount_amount,
        paid=order.paid,
        payment_status=order.payment_status.value if order.payment_status else None,
        total=order.total,
        items=[
            OrderItemSchema(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                portion_note=item.portion_note,
                total=item.total,
            )
            for item in order.items
        ],
        created_at=order.created_at,
    )

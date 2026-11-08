"""Router de pagos para pedidos (RF-P6-12/13/14, C1.0-C1.5 / RF-P11-06/08, C6).

Namespace: /api/v1/orders.
"""

import asyncio
import datetime
import io
import re
from csv import writer as csv_writer
from decimal import Decimal
from email.utils import format_datetime
from typing import Dict, List, Literal, Optional, Tuple, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi import status as http_status

from api.v1.dependencies import require_admin, get_current_user
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.orders.dependencies import (
    get_checkout_provider,
    get_customer_repository,
    get_now,
    get_order_repository,
    get_product_repository,
)
from api.v1.settings.dependencies import get_settings_repository
from api.v1.orders.schemas import (
    InsufficientStockItem,
    OrderCustomerResponse,
    OrderCreate,
    OrderDetailResponse,
    OrderItemBreakdown,
    OrderItemInput,
    OrderItemResponse,
    OrderListItem,
    OrderListResponse,
    OrderPreviewItemResponse,
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderStatusPatch,
    OrderUpdate,
    SnapshotLineResponse,
    WeeklyItem,
    WeeklyRange,
    WeeklySummaryResponse,
    WeeklyTotals,
    WhatsAppLinkResponse,
)
from api.v1.money import decimal_to_cents, format_money_cents
from api.v1.pdf.dependencies import get_pdf_client
from data.pdf.client import PdfClient
from api.v1.orders.schemas import OrderStatus as P6OrderStatus
from api.v1.orders.schemas import (
    OrderDetailSchema,
    OrderItemSchema,
    OrderListSchema,
    PaidResponse,
    PaymentInitResponse,
    PaymentStatusResponse,
    PortalOrderCreateRequest,
)
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.checkout_provider import CheckoutProvider, PaymentProviderError
from domain.models import User, UserRole
from domain.order import (
    DeliveryMode,
    Order,
    OrderItem,
    OrderStatus,
    OrderValidationError,
    PaymentMethod,
    PaymentStatus,
    is_payment_expired,
)
from domain.pricing_service import resolve_audience, derive_audience_price
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from domain.models import BusinessSettings, Ingredient, Product
from domain.order_pricing import price_order_item
from domain.orders import (
    InsufficientOrderStockError,
    InvalidStatusTransitionError,
    OrderItemSnapshot,
    OrderNotEditableError,
    transition_status,
)
from domain.orders import Order as P6Order
from domain.orders import OrderItem as P6OrderItem
from domain.pricing import UnitConversionError
from domain.repositories import (
    CustomerRepository,
    IngredientRepository,
    OrderRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases.transition_order_status import TransitionOrderStatus
from domain.use_cases import GetSettings

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
        marked = await repo.mark_paid_at(order.id, order.paid_at)
        if not marked:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="order_already_paid",
            )
        return PaidResponse(paid=True)
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


async def _expire_if_due(
    repo: SQLOrderRepository, order: Order, now: datetime.datetime
) -> Order:
    """Lazy 24 h expiry: cancel the order and release its coupon use."""
    if is_payment_expired(order, now) and await repo.expire_pending_payment(order.id):
        return await repo.get(order.id) or order
    return order


# ─── POST /orders/{id}/payment (C1.4) ───────────────────────────────

@router.post("/{id}/payment", response_model=PaymentInitResponse)
async def initiate_payment(
    id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    repo: SQLOrderRepository = Depends(get_order_repository),
    user: User = Depends(get_current_user),
    provider: CheckoutProvider = Depends(get_checkout_provider),
    now: datetime.datetime = Depends(get_now),
):
    """POST /orders/{id}/payment: inicia pago Mercado Pago (Checkout Pro).

    Dueño del pedido o admin. Solo pedidos status=nuevo +
    payment_method=mercadopago. Idempotencia por Idempotency-Key.
    """
    order = await _get_own_order(repo, id, user)
    order = await _expire_if_due(repo, order, now)

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

    # Row-guarded claim: exactly one concurrent initiation moves the order
    # to ``pending`` (RF-P6-12, RNF-P6-10); the others see 409/422.
    if not await repo.claim_payment_pending(order.id):
        current = await repo.get(order.id)
        if current is not None and (
            current.paid or current.payment_status in _FINAL_PAYMENT_STATUSES
        ):
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="payment_finalized",
            )
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="payment_in_progress",
        )

    amount = order.total - (order.discount_amount or Decimal("0"))
    try:
        result = await provider.create_payment(order.id, float(amount), _PAYMENT_CURRENCY)
    except PaymentProviderError as err:
        await repo.release_payment_pending(order.id)
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="payment_provider_error",
        ) from err
    except Exception:
        await repo.release_payment_pending(order.id)
        raise

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
    now: datetime.datetime = Depends(get_now),
):
    """GET /orders/{id}/payment: estado del pago (polling del portal).

    Dueño del pedido o admin; pedidos ajenos → 404.
    """
    order = await _get_own_order(repo, id, user)
    order = await _expire_if_due(repo, order, now)

    return PaymentStatusResponse(
        status=order.payment_status.value if order.payment_status else None,
        paid=order.paid,
        payment_reference=order.payment_reference,
        updated_at=order.created_at,
    )


def _retry_after_header(reopens_at: datetime.datetime | None) -> dict[str, str] | None:
    """``Retry-After`` (HTTP-date) when the window has a reopening time."""
    if reopens_at is None:
        return None
    if reopens_at.tzinfo is None:
        reopens_at = reopens_at.replace(tzinfo=datetime.UTC)
    return {"Retry-After": format_datetime(reopens_at, usegmt=True)}


# ─── C6 Portal endpoints: POST /orders, GET /orders/mine ────────────

@router.post("/", response_model=OrderDetailSchema)
async def create_order_portal(
    body: PortalOrderCreateRequest,
    user: User = Depends(get_current_user),
    repo: SQLOrderRepository = Depends(get_order_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo=Depends(get_settings_repository),
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
            headers=_retry_after_header(window.reopens_at),
        )

    # Validate payment_method
    try:
        payment_method = PaymentMethod(body.payment_method)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_payment_method",
        )

    try:
        delivery_mode = DeliveryMode(body.delivery_mode)
    except ValueError:
        delivery_mode = DeliveryMode.DELIVERY

    # Price and name come from the catalog, never from the request.
    audience = resolve_audience(user.role, None)
    business = await GetSettings(settings_repo).execute()
    items: list[OrderItem] = []
    for item_data in body.items:
        product = await ingredient_repo.get(item_data.product_id)
        if product is None:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="product_not_found",
            )
        items.append(
            OrderItem(
                product_id=item_data.product_id,
                product_name=product.name,
                quantity=item_data.quantity,
                unit_price=derive_audience_price(
                    product.price_per_unit, business.consumer_markup_pct, audience
                ),
                portion_note=item_data.portion_note,
            )
        )

    try:
        new_order = Order.place_portal(
            customer_id=user.id,
            date=body.date,
            items=items,
            payment_method=payment_method,
            delivery_mode=delivery_mode,
            delivery_address=body.delivery_address,
            coupon_code=body.coupon_code,
        )
    except OrderValidationError as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=err.code,
        ) from err
    await repo.add(new_order)

    # Fetch back and return
    result = await repo.get(new_order.id)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _iso_required(dt: Optional[datetime.datetime]) -> str:
    """Timestamps que la ORM siempre rellena (created_at/updated_at)."""
    assert dt is not None
    return dt.isoformat()


def _fmt_money(value: Decimal) -> str:
    """$81.000: entero sin decimales, separador de miles (display solo)."""
    integer = value.quantize(Decimal("1"))
    return f"${integer:,}".replace(",", ".")


def _breakdown_response(snapshot: OrderItemSnapshot) -> OrderItemBreakdown:
    return OrderItemBreakdown(
        materials=snapshot.materials,
        waste=snapshot.waste,
        materials_con_merma=snapshot.materials_con_merma,
        labor=snapshot.labor,
        gas=snapshot.gas,
        base=snapshot.base,
        margin_pct=snapshot.margin_pct,
        final=snapshot.final,
        rounded=snapshot.rounded,
    )


def _lines_response(snapshot: OrderItemSnapshot) -> List[SnapshotLineResponse]:
    return [
        SnapshotLineResponse(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            qty=line.qty,
            unit=line.unit,
            cost=line.cost,
            is_missing=line.is_missing,
        )
        for line in snapshot.lines
    ]


def _item_response(item: P6OrderItem, snapshot: OrderItemSnapshot) -> OrderItemResponse:
    return OrderItemResponse(
        product_id=item.product_id,
        product_name=item.product_name,
        qty=item.qty,
        portions=item.portions,
        note=item.note,
        complete=snapshot.complete,
        missing_ingredients=list(snapshot.missing),
        price=_breakdown_response(snapshot),
        lines=_lines_response(snapshot),
        rounded=snapshot.rounded,
    )


def _detail_response(
    order: P6Order, whatsapp_sent_at: Optional[datetime.datetime]
) -> OrderDetailResponse:
    return OrderDetailResponse(
        id=order.id or "",
        customer=OrderCustomerResponse(
            id=order.customer_id,
            name=order.customer_name,
            phone=order.customer_phone,
        ),
        date=order.date,
        status=cast(P6OrderStatus, order.status),
        margin_pct=order.margin_pct,
        items=[
            _item_response(item, order.snapshots[item.id or ""])
            for item in order.items
        ],
        total=order.total,
        whatsapp_sent_at=_iso(whatsapp_sent_at),
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
    )


async def _load_products(
    repo: ProductRepository, product_ids: List[str]
) -> Dict[str, Product]:
    by_id: Dict[str, Product] = {}
    for product_id in dict.fromkeys(product_ids):
        product = await repo.get(product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto desconocido o eliminado: {product_id}",
            )
        by_id[product_id] = product
    return by_id


async def _load_ingredients(repo: SQLIngredientRepository) -> Dict[str, Ingredient]:
    """Insumos activos paginados (los borrados quedan "missing" en el
    snapshot, mismo criterio que el costo de producto)."""
    by_id: Dict[str, Ingredient] = {}
    page = 1
    while True:
        items, total = await repo.list(None, None, page, 100)
        for item in items:
            by_id[item.id] = item
        if not items or len(by_id) >= total:
            break
        page += 1
    return by_id


def _price_items(
    products: Dict[str, Product],
    ingredients_by_id: Dict[str, Ingredient],
    settings: BusinessSettings,
    inputs: List[OrderItemInput],
    margin_override: Optional[Decimal],
) -> Tuple[List[P6OrderItem], Dict[str, OrderItemSnapshot]]:
    """Congela los snapshots de cada linea (RNF-P6-03)."""
    items: List[P6OrderItem] = []
    snapshots: Dict[str, OrderItemSnapshot] = {}
    for entry in inputs:
        product = products[entry.product_id]
        portions = (
            entry.portions if entry.portions is not None else product.servings
        )
        snapshot = price_order_item(
            product,
            ingredients_by_id,
            settings,
            qty=entry.qty,
            portions=portions,
            margin_override=margin_override,
        )
        item = P6OrderItem(
            product_id=product.id or "",
            qty=entry.qty,
            portions=portions,
            note=entry.note,
            product_name=product.name,
        )
        items.append(item)
        snapshots[item.id or ""] = snapshot
    return items, snapshots


def _whatsapp_message(order: P6Order) -> str:
    lines = [f"Hola {order.customer_name}:", ""]
    lines.append("Tu pedido:")
    for item in order.items:
        snapshot = order.snapshots[item.id or ""]
        lines.append(
            f"- {item.qty} x {item.product_name} "
            f"({item.portions} porciones) - {_fmt_money(snapshot.rounded)}"
        )
        if item.note:
            lines.append(f"  Nota: {item.note}")
    lines.append("")
    lines.append(f"Total: {_fmt_money(order.total)}")
    lines.append("")
    lines.append("Escribime para coordinar la entrega.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status_: Optional[str] = Query(
        default=None, alias="status", pattern="^(nuevo|confirmado|entregado|cancelado)$"
    ),
    customer_id: Optional[str] = Query(default=None, min_length=1, max_length=36),
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    date_from: Optional[datetime.date] = Query(default=None),
    date_to: Optional[datetime.date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    paid: Optional[bool] = Query(default=None),
    repo: OrderRepository = Depends(get_order_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado con filtros combinables: estado, cliente, nombre (sin
    acentos, RF-P2-02), rango de fechas (RF-P6-05) y estado de pago
    (RF-P6-10: `paid=true` solo pagados, `paid=false` solo sin pagar)."""
    orders, total = await repo.list_orders(
        status=status_,
        customer_id=customer_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        paid=paid,
    )
    return OrderListResponse(
        items=[
            OrderListItem(
                id=o.id or "",
                customer_name=o.customer_name,
                customer_phone=o.customer_phone,
                date=o.date,
                status=cast(P6OrderStatus, o.status),
                item_count=len(o.items),
                total=o.total,
                paid=o.paid,
                payment_method=o.payment_method,
                created_at=_iso(o.created_at),
            )
            for o in orders
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "", response_model=OrderDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_order(
    payload: OrderCreate,
    order_repo: OrderRepository = Depends(get_order_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: SQLIngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """UC-02: pedido nuevo con snapshots de precios congelados
    (RNF-P6-03). Cliente debe existir; los productos incompletos entran
    con costo 0 y desglose parcial (decision de negocio, 17/10)."""
    customer = await customer_repo.get(payload.customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    try:
        products = await _load_products(
            product_repo, [i.product_id for i in payload.items]
        )
        ingredients_by_id = await _load_ingredients(ingredient_repo)
        items, snapshots = _price_items(
            products, ingredients_by_id, settings, payload.items, payload.margin_pct
        )
    except UnitConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    order = P6Order(
        customer_id=customer.id or "",
        customer_name=customer.name,
        customer_phone=customer.phone,
        date=payload.date,
        margin_pct=payload.margin_pct,
        items=tuple(items),
        snapshots=snapshots,
    )
    created = await order_repo.create_full(order)
    return _detail_response(created, None)


@router.post("/preview", response_model=OrderPreviewResponse)
async def preview_order(
    payload: OrderPreviewRequest,
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: SQLIngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Cotizacion en vivo del wizard (admin): mismo calculo que el create,
    sin persistir. Devuelve el margen aplicado (override o tenant) y el
    total del pedido."""
    settings = await GetSettings(settings_repo).execute()
    try:
        products = await _load_products(
            product_repo, [i.product_id for i in payload.items]
        )
        ingredients_by_id = await _load_ingredients(ingredient_repo)
        items, snapshots = _price_items(
            products, ingredients_by_id, settings, payload.items, payload.margin_pct
        )
    except UnitConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    applied = payload.margin_pct if payload.margin_pct is not None else settings.margin_pct
    total = sum((snapshots[item.id or ""].rounded for item in items), Decimal("0"))
    return OrderPreviewResponse(
        margin_pct=applied,
        tenant_margin_pct=settings.margin_pct,
        items=[
            OrderPreviewItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                qty=item.qty,
                portions=item.portions,
                complete=snapshots[item.id or ""].complete,
                missing_ingredients=list(snapshots[item.id or ""].missing),
                price=_breakdown_response(snapshots[item.id or ""]),
                lines=_lines_response(snapshots[item.id or ""]),
                rounded=snapshots[item.id or ""].rounded,
            )
            for item in items
        ],
        total=total,
    )


# ─── Fase 5: resumen semanal + export (RF-P6-11) ────────────────────

_WEEK_ISO_RE = re.compile(r"^(\d{4})-W(\d{1,2})$")


def _parse_week(week: Optional[str]) -> Tuple[datetime.date, datetime.date]:
    """Resuelve la semana natural (Lun-Dom) a reportar (RF-P6-11).

    Acepta ISO week ``2026-W44`` o cualquier fecha ``2026-11-02`` dentro
    de la semana; ``None`` = semana actual del servidor.
    """
    if week is None or not week.strip():
        ref = datetime.date.today()
    else:
        w = week.strip().upper()
        m = _WEEK_ISO_RE.match(w)
        if m:
            try:
                ref = datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="week invalida: usa AAAA-Wnn (ej. 2026-W44) o una fecha AAAA-MM-DD",
                )
        else:
            try:
                ref = datetime.date.fromisoformat(week.strip())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="week invalida: usa AAAA-Wnn (ej. 2026-W44) o una fecha AAAA-MM-DD",
                )
    iso = ref.isocalendar()
    monday = datetime.date.fromisocalendar(iso[0], iso[1], 1)
    sunday = datetime.date.fromisocalendar(iso[0], iso[1], 7)
    return monday, sunday


async def _fetch_all_orders(
    repo: OrderRepository,
    status_: Optional[str],
    date_from: Optional[datetime.date],
    date_to: Optional[datetime.date],
    paid: Optional[bool],
) -> List[P6Order]:
    """Recorre todas las paginas del listado filtrado (export/resumen)."""
    orders: List[P6Order] = []
    page = 1
    while True:
        batch, total = await repo.list_orders(
            status=status_,
            customer_id=None,
            q=None,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=100,
            paid=paid,
        )
        orders.extend(batch)
        if not batch or len(orders) >= total:
            break
        page += 1
    return orders


def _orders_csv_rows(orders: List[P6Order]) -> List[List[str]]:
    """Filas CSV (con cabecera) del export de pedidos, dinero en
    formato legible $1.234,56 (format_money_cents, Fase 5)."""
    rows: List[List[str]] = [
        ["id", "cliente", "fecha", "items", "total", "estado", "pago", "metodo"]
    ]
    for o in orders:
        rows.append(
            [
                o.id or "",
                o.customer_name,
                o.date.isoformat(),
                str(len(o.items)),
                format_money_cents(decimal_to_cents(o.total)),
                o.status,
                "si" if o.paid else "no",
                o.payment_method,
            ]
        )
    return rows


def _csv_response(rows: List[List[str]], filename: str) -> StreamingResponse:
    """CSV streaming con csv.writer (escape correcto, mismo patron que
    la pricelist de productos)."""
    buf = io.StringIO()
    w = csv_writer(buf, lineterminator="\n")
    for row in rows:
        w.writerow(row)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/weekly", response_model=WeeklySummaryResponse)
async def weekly_summary(
    week: Optional[str] = Query(default=None, max_length=10),
    repo: OrderRepository = Depends(get_order_repository),
    _admin: User = Depends(require_admin),
):
    """Resumen semanal (RF-P6-11): pedidos confirmados/entregados de la
    semana natural (Lun-Dom) con totales de monto y estado de pago.
    Solo admin; `week` opcional (2026-W44 o fecha dentro de la semana)."""
    monday, sunday = _parse_week(week)
    orders: List[P6Order] = []
    for st in ("confirmado", "entregado"):
        orders.extend(
            await _fetch_all_orders(repo, st, monday, sunday, None)
        )
    orders.sort(key=lambda o: (o.date, o.customer_name))
    total_amount = sum((o.total for o in orders), Decimal("0"))
    paid_amount = sum((o.total for o in orders if o.paid), Decimal("0"))
    return WeeklySummaryResponse(
        week=WeeklyRange.model_validate({"from": monday, "to": sunday}),
        items=[
            WeeklyItem(
                id=o.id or "",
                customer=o.customer_name,
                date=o.date,
                items_count=len(o.items),
                total=decimal_to_cents(o.total),
                paid=o.paid,
                payment_method=o.payment_method,
            )
            for o in orders
        ],
        totals=WeeklyTotals(
            amount=decimal_to_cents(total_amount),
            paid=decimal_to_cents(paid_amount),
            unpaid=decimal_to_cents(total_amount - paid_amount),
        ),
    )


@router.get("/weekly/pdf")
async def weekly_summary_pdf(
    week: Optional[str] = Query(default=None, max_length=10),
    repo: OrderRepository = Depends(get_order_repository),
    pdf: PdfClient = Depends(get_pdf_client),
    _admin: User = Depends(require_admin),
):
    """PDF del resumen semanal (pdfgenerator, ADR-0001) — mismo dato que
    GET /orders/weekly (Fase 5, nuevo requerimiento de export)."""
    monday, sunday = _parse_week(week)
    orders: List[P6Order] = []
    for st in ("confirmado", "entregado"):
        orders.extend(await _fetch_all_orders(repo, st, monday, sunday, None))
    orders.sort(key=lambda o: (o.date, o.customer_name))

    total_cents = sum((decimal_to_cents(o.total) for o in orders), 0)
    paid_cents = sum((decimal_to_cents(o.total) for o in orders if o.paid), 0)
    payload = {
        "monday": monday.isoformat(),
        "sunday": sunday.isoformat(),
        "orders": [
            {
                "fecha": o.date.isoformat(),
                "cliente": o.customer_name,
                "items": len(o.items),
                "total_cents": decimal_to_cents(o.total),
                "paid": o.paid,
                "metodo": o.payment_method,
            }
            for o in orders
        ],
        "total_cents": total_cents,
        "paid_cents": paid_cents,
    }
    pdf_bytes = await asyncio.to_thread(pdf.render_weekly, payload)
    iso_week = monday.isocalendar()
    filename = f"resumen_semanal_{iso_week[0]}-W{iso_week[1]:02d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export")
async def export_orders(
    from_: Optional[datetime.date] = Query(default=None, alias="from"),
    to_: Optional[datetime.date] = Query(default=None, alias="to"),
    status_: Optional[str] = Query(
        default=None, alias="status", pattern="^(nuevo|confirmado|entregado|cancelado)$"
    ),
    paid: Optional[bool] = Query(default=None),
    fmt: Literal["csv", "pdf"] = Query(default="csv", alias="format"),
    repo: OrderRepository = Depends(get_order_repository),
    pdf: PdfClient = Depends(get_pdf_client),
    _admin: User = Depends(require_admin),
):
    """Export del listado de pedidos con los mismos filtros que
    GET /orders (fecha, estado, pago). CSV por defecto (backward-
    compatible); ``format=pdf`` genera PDF vía pdfgenerator (ADR-0001,
    sin archivo intermedio)."""
    orders = await _fetch_all_orders(repo, status_, from_, to_, paid)
    orders.sort(key=lambda o: (o.date, o.customer_name))
    if from_ and to_:
        period = f"{from_.isoformat()}_a_{to_.isoformat()}"
    else:
        period = "todos"
    if fmt == "csv":
        return _csv_response(_orders_csv_rows(orders), f"pedidos_{period}.csv")
    # PDF (pdfgenerator, ADR-0001)
    payload = {
        "period_label": period,
        "orders": [
            {
                "id": o.id or "",
                "cliente": o.customer_name,
                "fecha": o.date.isoformat(),
                "items": len(o.items),
                "total_cents": decimal_to_cents(o.total),
                "estado": o.status,
                "paid": o.paid,
                "metodo": o.payment_method,
            }
            for o in orders
        ],
    }
    pdf_bytes = await asyncio.to_thread(pdf.render_orders_export, payload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pedidos_{period}.pdf"'},
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    repo: OrderRepository = Depends(get_order_repository),
    current_user: User = Depends(get_current_user),
):
    """UC-03/UC-05: el desglose viene del snapshot congelado
    (RNF-P6-03), nunca recalculado contra el catalogo."""
    order = await repo.get_full(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
        )
    return _detail_response(order, order.whatsapp_sent_at)


@router.patch("/{order_id}", response_model=OrderDetailResponse)
async def update_order(
    order_id: str,
    payload: OrderUpdate,
    order_repo: OrderRepository = Depends(get_order_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: SQLIngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """UC-02: edicion parcial, solo estado `nuevo` (confirmado ya
    compromete stock y snapshot). Cambios de items o margin re-congelan
    los snapshots."""
    existing = await order_repo.get_full(order_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
        )
    if existing.status != "nuevo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se puede editar un pedido en estado nuevo",
        )
    provided = payload.model_dump(exclude_unset=True)
    settings = await GetSettings(settings_repo).execute()
    try:
        ingredients_by_id = await _load_ingredients(ingredient_repo)
        customer_id = provided.get("customer_id", existing.customer_id)
        customer = await customer_repo.get(customer_id)
        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
            )
        margin = provided.get("margin_pct", existing.margin_pct)
        if "items" in provided:
            assert payload.items is not None
            products = await _load_products(
                product_repo, [i.product_id for i in payload.items]
            )
            items, snapshots = _price_items(
                products, ingredients_by_id, settings, payload.items, margin
            )
        elif "margin_pct" in provided:
            products = await _load_products(
                product_repo, [item.product_id for item in existing.items]
            )
            inputs = [
                OrderItemInput(
                    product_id=item.product_id,
                    qty=item.qty,
                    portions=item.portions,
                    note=item.note,
                )
                for item in existing.items
            ]
            items, snapshots = _price_items(
                products, ingredients_by_id, settings, inputs, margin
            )
        else:
            items = list(existing.items)
            snapshots = dict(existing.snapshots)
    except UnitConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    order = P6Order(
        customer_id=customer.id or "",
        customer_name=customer.name,
        customer_phone=customer.phone,
        date=provided.get("date", existing.date),
        status=existing.status,
        margin_pct=margin,
        id=existing.id,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
        whatsapp_sent_at=existing.whatsapp_sent_at,
        items=tuple(items),
        snapshots=snapshots,
    )
    try:
        saved = await order_repo.update_full(order)
    except OrderNotEditableError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
        )
    return _detail_response(saved, saved.whatsapp_sent_at)


@router.patch("/{order_id}/status", response_model=OrderDetailResponse)
async def patch_order_status(
    order_id: str,
    payload: OrderStatusPatch,
    order_repo: SQLOrderRepository = Depends(get_order_repository),
    ingredient_repo: SQLIngredientRepository = Depends(get_ingredient_repository),
    _admin: User = Depends(require_admin),
):
    """RNF-P6-01: nuevo->confirmado->entregado; cancelado solo desde
    confirmado. Confirmar descuenta stock atomicamente (RNF-P6-02): si no
    alcanza, 409 con el detalle y cero cambios (RNF-P6-04). Cancelar
    reposiciona."""
    order = await order_repo.get_full(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
        )
    try:
        transition_status(order.status, payload.status)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        return await _apply_status(order, payload.status, order_repo, ingredient_repo)
    except InvalidStatusTransitionError as e:
        # Revalidado bajo lock en el repositorio (carrera con otro PATCH).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _apply_status(
    order: P6Order,
    target: str,
    order_repo: SQLOrderRepository,
    ingredient_repo: SQLIngredientRepository,
):
    try:
        updated = await TransitionOrderStatus(order_repo).execute(order.id, target)
    except InsufficientOrderStockError as e:
        details: List[InsufficientStockItem] = []
        for ingredient_id, faltante in e.shortage.items():
            row = await ingredient_repo.get(ingredient_id)
            # available/required capturados bajo lock (RNF-P6-04).
            available = e.available.get(ingredient_id, Decimal("0"))
            required = e.required.get(ingredient_id, available + faltante)
            details.append(
                InsufficientStockItem(
                    ingredient_id=ingredient_id,
                    ingredient_name=(
                        row.name if row is not None else "insumo borrado"
                    ),
                    available=available,
                    required=required,
                )
            )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "Stock insuficiente para confirmar el pedido",
                # JSONResponse no sabe serializar Decimal (RNF-P4-02):
                # el dinero viaja como str.
                "insufficient_stock": [
                    {
                        "ingredient_id": d.ingredient_id,
                        "ingredient_name": d.ingredient_name,
                        "available": str(d.available),
                        "required": str(d.required),
                    }
                    for d in details
                ],
            },
        )
    return _detail_response(updated, updated.whatsapp_sent_at)


@router.post("/{order_id}/whatsapp-link", response_model=WhatsAppLinkResponse)
async def whatsapp_link(
    order_id: str,
    repo: OrderRepository = Depends(get_order_repository),
    _admin: User = Depends(require_admin),
):
    """UC-03 CTA (RF-P6-06): link wa.me con el resumen del pedido; se
    registra el evento de auditoria."""
    order = await repo.get_full(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado"
        )
    message = _whatsapp_message(order)
    digits = "".join(ch for ch in order.customer_phone if ch.isdigit())
    url = f"https://wa.me/{digits}?text={quote(message)}"
    now = datetime.datetime.now(datetime.timezone.utc)
    await repo.mark_whatsapp_sent(order, now)
    return WhatsAppLinkResponse(url=url, message=message)

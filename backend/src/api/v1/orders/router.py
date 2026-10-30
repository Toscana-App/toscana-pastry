"""Router de pagos para pedidos (RF-P6-12/13/14, C1.0-C1.5 / RF-P11-06/08, C6).

Namespace: /api/v1/orders.
"""

import datetime
import uuid
from decimal import Decimal
from typing import cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi import status as http_status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.money import decimal_to_cents
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
)
from api.v1.orders.schemas import (
    InsufficientStockItem,
    OrderCreate,
    OrderCustomerResponse,
    OrderDetailResponse,
    OrderDetailSchema,
    OrderItemBreakdown,
    OrderItemInput,
    OrderItemResponse,
    OrderItemSchema,
    OrderListItem,
    OrderListResponse,
    OrderListSchema,
    OrderPreviewItemResponse,
    OrderPreviewRequest,
    OrderPreviewResponse,
)
from api.v1.orders.schemas import OrderStatus as P6OrderStatus
from api.v1.orders.schemas import (
    OrderStatusPatch,
    OrderUpdate,
    PaidResponse,
    PaymentInitResponse,
    PaymentStatusResponse,
    PortalOrderCreateRequest,
    SnapshotLineResponse,
    WhatsAppLinkResponse,
)
from api.v1.settings.dependencies import get_settings_repository
from data.models import OrderItemORM, OrderORM
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.mock_checkout_provider import MockCheckoutProvider
from domain.models import BusinessSettings, Ingredient, Product, User
from domain.order import (
    DeliveryMode,
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from domain.order_pricing import price_order_item
from domain.orders import (
    InsufficientOrderStockError,
    InvalidStatusTransitionError,
)
from domain.orders import Order as P6Order
from domain.orders import OrderItem as P6OrderItem
from domain.orders import OrderItemSnapshot, transition_status
from domain.pricing import UnitConversionError
from domain.repositories import (
    CustomerRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases import GetSettings

router = APIRouter(prefix="/orders", tags=["orders"])


async def _get_order_for_user(
    repo: SQLOrderRepository, order_id: str, user: User
) -> Order:
    """Returns the order when the user owns it (or is admin); 404 otherwise."""
    order = await repo.get(order_id)
    if order is None or (order.customer_id != user.id and user.role != "admin"):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Order not found"
        )
    return order


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
            reference=order.payment_reference or "manual",
            status=order.payment_status or PaymentStatus.APPROVED,
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
    current_user: User = Depends(get_current_user),
):
    """POST /orders/{id}/payment: inicia pago Mercado Pago.

    Accesible por el propietario del pedido (portal, RF-P11-10) o admin.
    Solo pedidos status=nuevo + payment_method=mercadopago.
    Idempotencia por Idempotency-Key.
    Pedidos ajenos → 404 (anti-sondeo).
    """
    order = await _get_order_for_user(repo, id, current_user)

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
    current_user: User = Depends(get_current_user),
):
    """GET /orders/{id}/payment: estado del pago (polling del portal, F3).

    Accesible por el propietario del pedido o admin; ajenos → 404.
    """
    order = await _get_order_for_user(repo, id, current_user)

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
    today = datetime.datetime.now(datetime.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    order_date = body.date.replace(tzinfo=None) if body.date.tzinfo else body.date
    if order_date < today:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_must_be_today_or_later",
        )

    # Validate payment_method
    try:
        payment_method = PaymentMethod(body.payment_method)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_payment_method",
        ) from e

    # Build items
    items = []
    for item_data in body.items:
        items.append(
            OrderItemORM(
                id=str(uuid.uuid4()),
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

    order_id = str(uuid.uuid4())
    order_code = f"TP{uuid.uuid4().hex[:6].upper()}"
    created_at = datetime.datetime.now(datetime.UTC)

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
    """GET /orders/mine/{code}: order detail by its code (RF-P11-08).

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


def _iso(dt: datetime.datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _iso_required(dt: datetime.datetime | None) -> str:
    """Timestamps que la ORM siempre rellena (created_at/updated_at)."""
    assert dt is not None
    return dt.isoformat()


def _fmt_money(value: Decimal) -> str:
    """$81.000: entero sin decimales, separador de miles (display solo)."""
    integer = value.quantize(Decimal("1"))
    return f"${integer:,}".replace(",", ".")


def _breakdown_response(snapshot: OrderItemSnapshot) -> OrderItemBreakdown:
    return OrderItemBreakdown(
        materials=decimal_to_cents(snapshot.materials),
        waste=decimal_to_cents(snapshot.waste),
        materials_con_merma=decimal_to_cents(snapshot.materials_con_merma),
        labor=decimal_to_cents(snapshot.labor),
        gas=decimal_to_cents(snapshot.gas),
        base=decimal_to_cents(snapshot.base),
        margin_pct=snapshot.margin_pct,
        final=decimal_to_cents(snapshot.final),
        rounded=decimal_to_cents(snapshot.rounded),
    )


def _lines_response(snapshot: OrderItemSnapshot) -> list[SnapshotLineResponse]:
    return [
        SnapshotLineResponse(
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient_name,
            qty=line.qty,
            unit=line.unit,
            cost=decimal_to_cents(line.cost),
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
        rounded=decimal_to_cents(snapshot.rounded),
    )


def _detail_response(
    order: P6Order, whatsapp_sent_at: datetime.datetime | None
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
        total=decimal_to_cents(order.total),
        whatsapp_sent_at=_iso(whatsapp_sent_at),
        created_at=_iso(order.created_at) or "",
        updated_at=_iso(order.updated_at) or "",
    )


async def _load_products(
    repo: ProductRepository, product_ids: list[str]
) -> dict[str, Product]:
    by_id: dict[str, Product] = {}
    for product_id in dict.fromkeys(product_ids):
        product = await repo.get(product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto desconocido o eliminado: {product_id}",
            )
        by_id[product_id] = product
    return by_id


async def _load_ingredients(repo: SQLIngredientRepository) -> dict[str, Ingredient]:
    """Insumos activos paginados (los borrados quedan "missing" en el
    snapshot, mismo criterio que el costo de producto)."""
    by_id: dict[str, Ingredient] = {}
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
    products: dict[str, Product],
    ingredients_by_id: dict[str, Ingredient],
    settings: BusinessSettings,
    inputs: list[OrderItemInput],
    margin_override: Decimal | None,
) -> tuple[list[P6OrderItem], dict[str, OrderItemSnapshot]]:
    """Congela los snapshots de cada linea (RNF-P6-03)."""
    items: list[P6OrderItem] = []
    snapshots: dict[str, OrderItemSnapshot] = {}
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
        assert item.id is not None, "P6OrderItem.id must not be None after __post_init__"
        snapshots[item.id] = snapshot
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
    status_: str | None = Query(
        default=None, alias="status", pattern="^(nuevo|confirmado|entregado|cancelado)$"
    ),
    customer_id: str | None = Query(default=None, min_length=1, max_length=36),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    date_from: datetime.date | None = Query(default=None),
    date_to: datetime.date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: SQLOrderRepository = Depends(get_order_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado con filtros combinables: estado, cliente, nombre (sin
    acentos, RF-P2-02) y rango de fechas (RF-P6-05)."""
    orders, total = await repo.list_orders(
        status=status_,
        customer_id=customer_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
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
                total=decimal_to_cents(o.total),
                created_at=_iso(o.created_at) or "",
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
    order_repo: SQLOrderRepository = Depends(get_order_repository),
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
        ) from e
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
        ) from e
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
                rounded=decimal_to_cents(snapshots[item.id or ""].rounded),
            )
            for item in items
        ],
        total=decimal_to_cents(total),
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    repo: SQLOrderRepository = Depends(get_order_repository),
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
    order_repo: SQLOrderRepository = Depends(get_order_repository),
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
        ) from e

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
    saved = await order_repo.update_full(order)
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if payload.status == "confirmado":
        try:
            updated = await order_repo.confirm(order)
        except InsufficientOrderStockError as e:
            details: list[InsufficientStockItem] = []
            for ingredient_id, faltante in e.shortage.items():
                row = await ingredient_repo.get(ingredient_id)
                available = (
                    row.stock_qty if row is not None else Decimal("0")
                )
                details.append(
                    InsufficientStockItem(
                        ingredient_id=ingredient_id,
                        ingredient_name=(
                            row.name if row is not None else "insumo borrado"
                        ),
                        available=available,
                        # el dominio guarda el FALTANTE; la API reporta el
                        # requerido total.
                        required=available + faltante,
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
    elif payload.status == "cancelado":
        updated = await order_repo.cancel(order)
    else:  # entregado
        updated = await order_repo.mark_delivered(order)
    return _detail_response(updated, updated.whatsapp_sent_at)


@router.post("/{order_id}/whatsapp-link", response_model=WhatsAppLinkResponse)
async def whatsapp_link(
    order_id: str,
    repo: SQLOrderRepository = Depends(get_order_repository),
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
    url = f"https://wa.me/{order.customer_phone}?text={quote(message)}"
    now = datetime.datetime.now(datetime.UTC)
    await repo.mark_whatsapp_sent(order, now)
    return WhatsAppLinkResponse(url=url, message=message)

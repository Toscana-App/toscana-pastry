"""Pedidos (Fase 6, P6).

Flujo de negocio:
  crear (nuevo) -> confirmar (descuento de stock atomico) -> entregar
                     \\-> cancelar (reposicion de stock)

Reglas clave:
- El desglose se congela al crear (RNF-P6-03): las lecturas nunca
  recalculan contra el catalogo; los cambios de receta/precios no tocan
  el historial.
- Confirmar descuenta stock en una sola transaccion (RNF-P6-02); si no
  alcanza, 409 con el detalle y NINGUN cambio queda aplicado (RNF-P6-04).
- Cancelar solo desde confirmado, y reposiciona (RNF-P6-01).
- CTA de WhatsApp (RF-P6-06): el link wa.me se genera aca y el evento se
  registra (auditoria).
"""
import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
)
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
    OrderStatus,
    OrderUpdate,
    SnapshotLineResponse,
    WhatsAppLinkResponse,
)
from api.v1.settings.dependencies import get_settings_repository
from domain.use_cases import GetSettings
from domain.use_cases.transition_order_status import TransitionOrderStatus
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_product_repository import SQLProductRepository
from domain.models import BusinessSettings, Ingredient, Product, User
from domain.order_pricing import price_order_item
from domain.orders import (
    InsufficientOrderStockError,
    InvalidStatusTransitionError,
    Order,
    OrderItem,
    OrderItemSnapshot,
    OrderNotEditableError,
    transition_status,
)
from domain.pricing import UnitConversionError
from domain.repositories import (
    CustomerRepository,
    OrderRepository,
    ProductRepository,
    SettingsRepository,
)

router = APIRouter(prefix="/orders", tags=["orders"])


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


def _item_response(item: OrderItem, snapshot: OrderItemSnapshot) -> OrderItemResponse:
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
    order: Order, whatsapp_sent_at: Optional[datetime.datetime]
) -> OrderDetailResponse:
    return OrderDetailResponse(
        id=order.id or "",
        customer=OrderCustomerResponse(
            id=order.customer_id,
            name=order.customer_name,
            phone=order.customer_phone,
        ),
        date=order.date,
        status=cast(OrderStatus, order.status),
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
) -> Tuple[List[OrderItem], Dict[str, OrderItemSnapshot]]:
    """Congela los snapshots de cada linea (RNF-P6-03)."""
    items: List[OrderItem] = []
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
        item = OrderItem(
            product_id=product.id or "",
            qty=entry.qty,
            portions=portions,
            note=entry.note,
            product_name=product.name,
        )
        items.append(item)
        snapshots[item.id or ""] = snapshot
    return items, snapshots


def _whatsapp_message(order: Order) -> str:
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
    repo: OrderRepository = Depends(get_order_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado con filtros combinables: estado, cliente, nombre (sin
    acentos, RF-P2-02) y rango de fechas (RF-P6-05)."""
    orders, total = await repo.list(
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
                status=cast(OrderStatus, o.status),
                item_count=len(o.items),
                total=o.total,
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
    order = Order(
        customer_id=customer.id or "",
        customer_name=customer.name,
        customer_phone=customer.phone,
        date=payload.date,
        margin_pct=payload.margin_pct,
        items=tuple(items),
        snapshots=snapshots,
    )
    created = await order_repo.create(order)
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


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    repo: OrderRepository = Depends(get_order_repository),
    current_user: User = Depends(get_current_user),
):
    """UC-03/UC-05: el desglose viene del snapshot congelado
    (RNF-P6-03), nunca recalculado contra el catalogo."""
    order = await repo.get(order_id)
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
    existing = await order_repo.get(order_id)
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

    order = Order(
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
        saved = await order_repo.update(order)
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
    order = await order_repo.get(order_id)
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
    order: Order,
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
    order = await repo.get(order_id)
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

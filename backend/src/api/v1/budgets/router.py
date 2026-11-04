"""Presupuestos (Fase 7, P7/P8).

Flujo de negocio:
  wizard (cliente + items + margen/modo) -> borrador #000NN
      -> editar/recalcular (refleja el catalogo corriente)
      -> enviar (enviado, snapshot de version) -> reenviar (version nueva)
      \-> convertir en pedido (pedido `nuevo` con snapshots propios, RNF-P6-03)

Reglas clave:
- El costo por unidad se deriva contra el catalogo al escribir (create,
  update, recalculate); la lectura NUNCA vuelve al catalogo: guarda
  unit_cost/unit_selling por item y los totales son puro dominio.
- La secuencia #000NN se asigna en la creacion (RNF-P8-04), sin reuso.
- El presupuesto NO toca stock: ni al crear, ni al convertir (el stock
  se descuenta al confirmar el pedido, RNF-P6-02).
- Money viaja en centavos (RF-P8-03) y Pct como string (money.py).
"""
import datetime
import io
from csv import writer as csv_writer
from decimal import Decimal
from typing import Dict, List, Literal, Optional, Tuple, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from api.v1.budgets.dependencies import get_budget_repository
from api.v1.budgets.schemas import (
    BudgetCreate,
    BudgetDetailResponse,
    BudgetItemInput,
    BudgetItemResponse,
    BudgetItemsPatch,
    BudgetListItem,
    BudgetListResponse,
    BudgetSummary,
    BudgetUpdate,
    BudgetStatus,
    CalculationMode,
    ConvertToOrderResponse,
    RecalculateResponse,
    WhatsAppLinkResponse,
)
from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.money import cents_to_decimal, decimal_to_cents
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
)
from api.v1.orders.schemas import OrderItemInput
from api.v1.pdf.signing import make_share_token
from api.v1.settings.dependencies import get_settings_repository
from core.config import settings as app_settings
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from domain.budget_pricing import unit_product_cost
from domain.budgets import (
    Budget,
    BudgetAlreadyConvertedError,
    BudgetNotConvertibleError,
    CalculationMode as CalcMode,
    NoBudgetChangesError,
    transition_to_sent,
)
from domain.models import BusinessSettings, User
from domain.pricing import UnitConversionError
from domain.repositories import (
    BudgetRepository,
    CustomerRepository,
    IngredientRepository,
    OrderRepository,
    ProductRepository,
    SettingsRepository,
)
from domain.use_cases import (
    BudgetItemDraft,
    BudgetNotFoundError,
    ConvertBudgetToOrder,
    DeriveBudgetItems,
    GetSettings,
    UnknownProductError,
)
from domain.whatsapp import (
    WHATSAPP_DAILY_LIMIT,
    budget_whatsapp_message,
    mask_phone,
    normalize_e164_ar,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso(dt: Optional[datetime.datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _item_response(item) -> BudgetItemResponse:
    return BudgetItemResponse(
        product_id=item.product_id,
        product_name=item.product_name,
        qty=item.qty,
        unit_cost=item.unit_cost,
        unit_selling=item.unit_selling,
        line_cost=item.line_cost,
        line_selling=item.line_selling,
        price_overridden=item.price_overridden,
    )


def _summary(budget: Budget) -> BudgetSummary:
    totals = budget.totals
    return BudgetSummary(
        subtotal=totals.subtotal,
        total_costos=totals.total_costos,
        ganancia=totals.ganancia,
        total_venta=totals.total_venta,
    )


def _detail_response(budget: Budget) -> BudgetDetailResponse:
    return BudgetDetailResponse(
        id=budget.id or "",
        seq=budget.seq,
        customer={
            "id": budget.customer_id,
            "name": budget.customer_name,
            "phone": budget.customer_phone,
        },
        delivery_address=budget.delivery_address,
        status=cast(BudgetStatus, budget.status),
        calculation_mode=cast(CalculationMode, budget.calculation_mode.value),
        margin_pct=budget.margin_pct,
        version=budget.version,
        items=[_item_response(item) for item in budget.items],
        summary=_summary(budget),
        created_at=budget.created_at.isoformat(),
        updated_at=budget.updated_at.isoformat(),
        sent_at=_iso(budget.sent_at),
    )


async def _derive_items(
    product_repo: ProductRepository,
    ingredient_repo: IngredientRepository,
    settings: BusinessSettings,
    inputs: List[BudgetItemInput],
    margin_override: Optional[Decimal],
    mode: CalcMode,
) -> Tuple[list, Decimal]:
    """Mapea la entrada HTTP (centavos) al caso de uso y sus errores a 400."""
    drafts = [
        BudgetItemDraft(
            product_id=i.product_id,
            qty=i.qty,
            price_override=(
                cents_to_decimal(i.price_override)
                if i.price_override is not None
                else None
            ),
        )
        for i in inputs
    ]
    try:
        return await DeriveBudgetItems(product_repo, ingredient_repo).execute(
            settings, drafts, margin_override, mode
        )
    except (UnknownProductError, UnitConversionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=BudgetListResponse)
async def list_budgets(
    q: Optional[str] = Query(default=None, min_length=1, max_length=120),
    status_: Optional[str] = Query(
        default=None, alias="status", pattern="^(borrador|enviado)$"
    ),
    date_from: Optional[datetime.date] = Query(default=None, alias="from"),
    date_to: Optional[datetime.date] = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: BudgetRepository = Depends(get_budget_repository),
    current_user: User = Depends(get_current_user),
):
    """Listado con busqueda por secuencia (#00042) o cliente (sin
    acentos), estado y rango de fechas de creacion."""
    budgets, total = await repo.list(
        status=status_, q=q, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    return BudgetListResponse(
        items=[
            BudgetListItem(
                id=b.id or "",
                seq=b.seq,
                customer_name=b.customer_name,
                customer_phone=b.customer_phone,
                status=cast(BudgetStatus, b.status),
                item_count=len(b.items),
                total=b.totals.subtotal,
                version=b.version,
                created_at=_iso(b.created_at) or "",
                sent_at=_iso(b.sent_at),
            )
            for b in budgets
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_budgets(
    status_: Optional[str] = Query(
        default=None, alias="status", pattern="^(borrador|enviado)$"
    ),
    from_: Optional[datetime.date] = Query(default=None, alias="from"),
    to_: Optional[datetime.date] = Query(default=None, alias="to"),
    fmt: Literal["csv", "pdf"] = Query(default="csv", alias="format"),
    repo: BudgetRepository = Depends(get_budget_repository),
    _admin: User = Depends(require_admin),
):
    """Export del listado de presupuestos (mismos filtros que
    GET /budgets). CSV por defecto (backward-compatible);
    ``format=pdf`` genera PDF con PyMuPDF en memoria (Fase 5, sin
    archivo intermedio). Columnas: secuencia, cliente, teléfono, fecha
    de creación, enviado, estado y total de venta."""
    budgets: List[Budget] = []
    page = 1
    while True:
        batch, total = await repo.list(
            status=status_, q=None, date_from=from_, date_to=to_,
            page=page, page_size=100,
        )
        budgets.extend(batch)
        if not batch or len(budgets) >= total:
            break
        page += 1
    budgets.sort(key=lambda b: b.seq)

    def _tuple(b: Budget) -> tuple[str, str, str, datetime.date, datetime.date | None, str, int]:
        return (
            b.seq,
            b.customer_name,
            b.customer_phone,
            b.created_at.date(),
            b.sent_at.date() if b.sent_at else None,
            b.status,
            decimal_to_cents(b.totals.total_venta),
        )

    period_label = (
        f"{from_.isoformat()} a {to_.isoformat()}" if from_ and to_ else "todos"
    )
    period_slug = (
        f"{from_.isoformat()}_a_{to_.isoformat()}" if from_ and to_ else "todos"
    )
    if fmt == "csv":
        from data.pdf_export.pymupdf_renderer import format_money_cents

        rows = [
            ["seq", "cliente", "telefono", "fecha", "enviado", "estado",
             "total_venta"]
        ]
        for seq, cliente, telefono, fecha, enviado, estado, total_cents in (
            _tuple(b) for b in budgets
        ):
            rows.append(
                [
                    f"#{seq}",
                    cliente,
                    telefono,
                    fecha.strftime("%d/%m/%Y"),
                    enviado.strftime("%d/%m/%Y") if enviado else "",
                    estado,
                    format_money_cents(total_cents),
                ]
            )
        buf = io.StringIO()
        w = csv_writer(buf, lineterminator="\n")
        for row in rows:
            w.writerow(row)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="presupuestos_{period_slug}.csv"'
            },
        )
    # PDF
    from data.pdf_export.pymupdf_renderer import render_budgets_export_pdf

    pdf_bytes = render_budgets_export_pdf(period_label, [_tuple(b) for b in budgets])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="presupuestos_{period_slug}.pdf"'
        },
    )


@router.post(
    "", response_model=BudgetDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_budget(
    payload: BudgetCreate,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Alta del wizard completo (P7): cliente ya resuelto (el frontend
    crea/reutiliza via /customers), items con qty, margen y modo de
    calculo. Asigna la secuencia #000NN (RNF-P8-04)."""
    customer = await customer_repo.get(payload.customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    items, _margin = await _derive_items(
        product_repo,
        ingredient_repo,
        settings,
        payload.items,
        payload.margin_pct,
        CalcMode(payload.calculation_mode),
    )
    budget = Budget(
        customer_id=customer.id or "",
        customer_name=customer.name,
        customer_phone=customer.phone,
        # Snapshot (RNF-P7-04): explicito en el wizard; si no, hereda la
        # direccion del cliente.
        delivery_address=(
            payload.delivery_address
            if payload.delivery_address is not None
            else customer.delivery_address
        ),
        items=tuple(items),
        margin_pct=payload.margin_pct,
        calculation_mode=CalcMode(payload.calculation_mode),
    )
    created = await budget_repo.create(budget)
    return _detail_response(created)


@router.get("/{budget_id}", response_model=BudgetDetailResponse)
async def get_budget(
    budget_id: str,
    repo: BudgetRepository = Depends(get_budget_repository),
    current_user: User = Depends(get_current_user),
):
    """Detalle: items + totales derivados de lo guardado (nunca
    recalcula contra el catalogo)."""
    budget = await repo.get(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return _detail_response(budget)


@router.put("/{budget_id}", response_model=BudgetDetailResponse)
async def update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Edicion parcial (borrador y enviado: el reenviar crea version
    nueva, RF-P8-05). Cambios de items/margen/modo re-derivan contra el
    catalogo corriente."""
    existing = await budget_repo.get(budget_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    provided = payload.model_dump(exclude_unset=True)
    settings = await GetSettings(settings_repo).execute()
    customer_id = provided.get("customer_id", existing.customer_id)
    customer = await customer_repo.get(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado"
        )
    margin = provided.get("margin_pct", existing.margin_pct)
    mode = CalcMode(
        provided.get("calculation_mode", existing.calculation_mode.value)
    )
    # Direccion de entrega (RNF-P7-04): explicito reemplaza; cambio de
    # cliente hereda la suya; en caso contrario conserva el snapshot.
    if "delivery_address" in provided:
        address = provided["delivery_address"]
    elif "customer_id" in provided:
        address = customer.delivery_address
    else:
        address = existing.delivery_address
    if "items" in provided:
        assert payload.items is not None
        items, _ = await _derive_items(
            product_repo, ingredient_repo, settings, payload.items, margin, mode
        )
    else:
        # Sin items: re-derivar los existentes contra el catalogo (un
        # cambio de margen/modo cambia los precios, RF-P8 "recalcula").
        inputs = [
            BudgetItemInput(
                product_id=item.product_id,
                qty=item.qty,
                price_override=None,
            )
            for item in existing.items
        ]
        if mode == CalcMode.MANUAL:
            # Conservar los overrides de los items existentes.
            inputs = [
                BudgetItemInput(
                    product_id=item.product_id,
                    qty=item.qty,
                    price_override=(
                        int(item.unit_selling * 100) if item.price_overridden else None
                    ),
                )
                for item in existing.items
            ]
        items, _ = await _derive_items(
            product_repo, ingredient_repo, settings, inputs, margin, mode
        )
    updated = Budget(
        customer_id=customer.id or "",
        customer_name=customer.name,
        customer_phone=customer.phone,
        delivery_address=address,
        items=tuple(items),
        margin_pct=margin,
        calculation_mode=mode,
        status=existing.status,
        version=existing.version,
        seq=existing.seq,
        id=existing.id,
        created_at=existing.created_at,
        sent_at=existing.sent_at,
    )
    saved = await budget_repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return _detail_response(saved)


@router.patch("/{budget_id}/items", response_model=BudgetDetailResponse)
async def patch_budget_items(
    budget_id: str,
    payload: BudgetItemsPatch,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Ajuste de lineas (qty/overrides) con el margen/modo corrientes."""
    existing = await budget_repo.get(budget_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    items, _ = await _derive_items(
        product_repo,
        ingredient_repo,
        settings,
        payload.items,
        existing.margin_pct,
        existing.calculation_mode,
    )
    updated = Budget(
        customer_id=existing.customer_id,
        customer_name=existing.customer_name,
        customer_phone=existing.customer_phone,
        delivery_address=existing.delivery_address,
        items=tuple(items),
        margin_pct=existing.margin_pct,
        calculation_mode=existing.calculation_mode,
        status=existing.status,
        version=existing.version,
        seq=existing.seq,
        id=existing.id,
        created_at=existing.created_at,
        sent_at=existing.sent_at,
    )
    saved = await budget_repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return _detail_response(saved)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: str,
    repo: BudgetRepository = Depends(get_budget_repository),
    _admin: User = Depends(require_admin),
):
    """Borrado duro. Sin efecto sobre stock ni secuencia (RNF-P8)."""
    deleted = await repo.delete(budget_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{budget_id}/recalculate", response_model=RecalculateResponse)
async def recalculate_budget(
    budget_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Recalcula costos contra el catalogo corriente (cambios de
    precios de insumos/receta) y re-deriva los precios de venta. Los
    totales reflejan el nuevo estado (RF-P8 'Recalcula')."""
    existing = await budget_repo.get(budget_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    settings = await GetSettings(settings_repo).execute()
    inputs = [
        BudgetItemInput(
            product_id=item.product_id,
            qty=item.qty,
            price_override=(
                int(item.unit_selling * 100) if item.price_overridden else None
            ),
        )
        for item in existing.items
    ]
    items, margin_applied = await _derive_items(
        product_repo,
        ingredient_repo,
        settings,
        inputs,
        existing.margin_pct,
        existing.calculation_mode,
    )
    updated = Budget(
        customer_id=existing.customer_id,
        customer_name=existing.customer_name,
        customer_phone=existing.customer_phone,
        delivery_address=existing.delivery_address,
        items=tuple(items),
        margin_pct=existing.margin_pct,
        calculation_mode=existing.calculation_mode,
        status=existing.status,
        version=existing.version,
        seq=existing.seq,
        id=existing.id,
        created_at=existing.created_at,
        sent_at=existing.sent_at,
    )
    saved = await budget_repo.update(updated)
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    return RecalculateResponse(
        summary=_summary(saved), margin_applied=margin_applied
    )


@router.post(
    "/{budget_id}/convert-to-order",
    response_model=ConvertToOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def convert_to_order(
    budget_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    order_repo: OrderRepository = Depends(get_order_repository),
    product_repo: ProductRepository = Depends(get_product_repository),
    ingredient_repo: IngredientRepository = Depends(get_ingredient_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """Convierte en pedido (RF-P8-02, RF-P8-08): solo presupuestos
    `enviado`, una sola vez (409 `already_converted`). La orquestacion
    vive en el caso de uso ConvertBudgetToOrder."""
    use_case = ConvertBudgetToOrder(
        budget_repo, order_repo, product_repo, ingredient_repo, settings_repo
    )
    try:
        result = await use_case.execute(budget_id)
    except BudgetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    except BudgetAlreadyConvertedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_converted"
        )
    except BudgetNotConvertibleError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="budget_not_sent"
        )
    except (UnknownProductError, UnitConversionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ConvertToOrderResponse(order_id=result.order_id, seq=result.seq)


@router.post("/{budget_id}/send", response_model=BudgetDetailResponse)
async def send_budget(
    budget_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    _admin: User = Depends(require_admin),
):
    """Envia (RF-P8-05): borrador -> enviado (version 1, snapshot) o
    reenviar con cambios (version nueva). Sin cambios: 409."""
    budget = await budget_repo.get(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Presupuesto no encontrado"
        )
    try:
        sent = transition_to_sent(budget)
    except NoBudgetChangesError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    saved = await budget_repo.mark_sent(sent)
    return _detail_response(saved)


@router.post("/{budget_id}/whatsapp-link", response_model=WhatsAppLinkResponse)
async def budget_whatsapp_link(
    budget_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    """P10 (UC-01): wa.me prellenado con la plantilla (saludo, ítems,
    total, firma) y el link firmado al PDF (72 h). Registra el envío con
    el teléfono enmascarado (RNF-P10-05) y aplica el límite de 30 links/
    día (RF-P10-06). El cliente solo presiona 'enviar' en WhatsApp."""
    budget = await budget_repo.get(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    try:
        e164 = normalize_e164_ar(budget.customer_phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    now = datetime.datetime.now(datetime.timezone.utc)
    settings = await GetSettings(settings_repo).execute()
    token, _expires = make_share_token(budget.id, app_settings.SECRET_KEY)
    share_url = f"{app_settings.PUBLIC_BASE_URL}/api/v1/pdf/{token}"
    message = budget_whatsapp_message(
        budget, settings.business_name or "", share_url
    )
    url = f"https://wa.me/{e164}?text={quote(message)}"
    # Conteo + registro atómicos (RF-P10-06): sin carrera entre el chequeo
    # del límite y el INSERT.
    sent_at = await budget_repo.record_whatsapp_sent_within_limit(
        budget.id,
        mask_phone(e164),
        now - datetime.timedelta(days=1),
        WHATSAPP_DAILY_LIMIT,
    )
    if sent_at is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Límite diario de links de WhatsApp alcanzado (30/día)",
        )
    return WhatsAppLinkResponse(url=url, sent_at=sent_at.isoformat())

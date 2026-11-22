import asyncio
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.v1.dependencies import require_admin
from api.v1.invoicing.dependencies import (
    get_afip_client,
    get_invoice_pdf_renderer,
    get_invoice_repository,
    get_invoicing_order_repository,
)
from api.v1.invoicing.schemas import (
    InvoiceCreate,
    InvoiceDetail,
    InvoiceDetailResponse,
    InvoiceItemResponse,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceResponse,
    InvoicingSettingsPayload,
    InvoicingSettingsResponse,
    InvoicingSettingsSaved,
)
from api.v1.money import cents_to_decimal, decimal_to_cents
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.invoicing import (
    ESTADO_APROBADO,
    AfipClient,
    AfipCredentialMissingError,
    AfipUnavailableError,
    AfipWsfeError,
    Invoice,
    InvoiceItem,
    InvoiceValidationError,
    InvoicingNotConfiguredError,
    InvoicingSettings,
)
from domain.models import User
from domain.pdf import InvoicePdfRenderer, invoice_arca_pdf_payload
from domain.use_cases.issue_invoice import (
    IssueInvoice,
    IssueInvoiceRequest,
    OrderNotFoundError,
)

logger = logging.getLogger("invoicing")

router = APIRouter(tags=["invoicing"])

NOT_CONFIGURED = "invoicing_not_configured"
CREDENTIAL_MISSING = "afip_credential_missing"
AFIP_UNAVAILABLE = "afip_unavailable"


def _pdf_url(invoice: Invoice) -> str:
    return f"/api/v1/invoices/{invoice.id}/pdf"


def _item_request(items) -> tuple[InvoiceItem, ...]:
    if not items:
        return ()
    return tuple(
        InvoiceItem(
            descripcion=item.descripcion,
            cantidad=Decimal(item.cantidad),
            precio_unit=str(cents_to_decimal(item.precio_unit)),
            position=index,
        )
        for index, item in enumerate(items, start=1)
    )


def _item_response(item: InvoiceItem) -> InvoiceItemResponse:
    return InvoiceItemResponse(
        descripcion=item.descripcion,
        cantidad=int(item.cantidad),
        precio_unit=decimal_to_cents(Decimal(item.precio_unit)),
    )


def _imp_total(invoice: Invoice) -> int:
    return decimal_to_cents(Decimal(invoice.imp_total))


def _list_item(invoice: Invoice) -> InvoiceListItem:
    return InvoiceListItem(
        id=invoice.id,
        order_id=invoice.order_id,
        punto_venta=invoice.punto_venta,
        tipo_cbte=invoice.tipo_cbte,
        numero=invoice.numero,
        cae=invoice.cae,
        cae_vto=invoice.cae_vto,
        fecha=invoice.fecha,
        imp_total=_imp_total(invoice),
        estado=invoice.estado,
        created_at=invoice.created_at,
    )


def _response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        order_id=invoice.order_id,
        punto_venta=invoice.punto_venta,
        tipo_cbte=invoice.tipo_cbte,
        numero=invoice.numero,
        cae=invoice.cae,
        cae_vto=invoice.cae_vto,
        fecha=invoice.fecha,
        imp_total=_imp_total(invoice),
        estado=invoice.estado,
        pdf_url=_pdf_url(invoice),
    )


def _detail(invoice: Invoice) -> InvoiceDetail:
    return InvoiceDetail(
        id=invoice.id,
        order_id=invoice.order_id,
        punto_venta=invoice.punto_venta,
        tipo_cbte=invoice.tipo_cbte,
        numero=invoice.numero,
        cae=invoice.cae,
        cae_vto=invoice.cae_vto,
        fecha=invoice.fecha,
        imp_total=_imp_total(invoice),
        estado=invoice.estado,
        condicion_iva=invoice.condicion_iva,
        receptor_doc_tipo=invoice.receptor_doc_tipo,
        receptor_doc_nro=invoice.receptor_doc_nro,
        receptor_nombre=invoice.receptor_nombre,
        created_at=invoice.created_at,
        pdf_url=_pdf_url(invoice),
    )


def _settings_payload(settings: InvoicingSettings) -> InvoicingSettingsPayload:
    return InvoicingSettingsPayload(
        cuit=settings.cuit,
        punto_venta=settings.punto_venta,
        razon_social=settings.razon_social,
        domicilio=settings.domicilio,
        condicion_iva=settings.condicion_iva,
        categoria_monotributo=settings.categoria_monotributo,
        ingresos_brutos=settings.ingresos_brutos,
        inicio_actividades=settings.inicio_actividades,
    )


def _settings_response(settings: InvoicingSettings | None) -> InvoicingSettingsResponse:
    if settings is None:
        return InvoicingSettingsResponse(configured=False, settings=None)
    return InvoicingSettingsResponse(configured=True, settings=_settings_payload(settings))


def _existing_invoice_body(existing: Invoice) -> dict:
    return {
        "detail": "pedido_ya_facturado",
        "existing_invoice": _response(existing).model_dump(mode="json"),
    }


@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    payload: InvoiceCreate,
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    order_repo: SQLOrderRepository = Depends(get_invoicing_order_repository),
    afip_client: AfipClient = Depends(get_afip_client),
    current_user: User = Depends(require_admin),
):
    use_case = IssueInvoice(
        invoice_repository=invoice_repo,
        order_repository=order_repo,
        afip_client=afip_client,
    )
    request = IssueInvoiceRequest(
        order_id=payload.order_id,
        concepto=payload.concepto,
        doc_tipo=payload.doc_tipo,
        doc_nro=payload.doc_nro,
        receptor_nombre=payload.receptor_nombre,
        fch_serv_desde=payload.fch_serv_desde,
        fch_serv_hasta=payload.fch_serv_hasta,
        items=_item_request(payload.items),
    )
    try:
        invoice = await use_case.execute(request)
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="pedido_no_encontrado"
        )
    except InvoiceValidationError as exc:
        if exc.code == "pedido_ya_facturado":
            existing = getattr(exc, "invoice", None)
            if existing is not None:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content=_existing_invoice_body(existing),
                )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.code
        ) from None
    except InvoicingNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_CONFIGURED
        ) from None
    except AfipCredentialMissingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=CREDENTIAL_MISSING,
        ) from None
    except AfipUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=AFIP_UNAVAILABLE
        ) from None
    except AfipWsfeError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": "comprobante_rechazado",
                "observaciones": list(exc.observaciones),
            },
        )

    logger.info(
        "invoice_issued order_id=%s invoice_id=%s punto_venta=%s tipo_cbte=%s "
        "numero=%s cae=%s user=%s",
        invoice.order_id,
        invoice.id,
        invoice.punto_venta,
        invoice.tipo_cbte,
        invoice.numero,
        invoice.cae,
        getattr(current_user, "id", None),
    )
    return _response(invoice)


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    order_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    _admin: User = Depends(require_admin),
):
    invoices, total = await invoice_repo.list(
        order_id=order_id, page=page, page_size=page_size
    )
    return InvoiceListResponse(
        items=[_list_item(invoice) for invoice in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
async def get_invoice(
    invoice_id: str,
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    _admin: User = Depends(require_admin),
):
    invoice = await invoice_repo.get(invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="comprobante_no_encontrado"
        )
    return InvoiceDetailResponse(
        invoice=_detail(invoice),
        items=[_item_response(item) for item in invoice.items],
        observaciones=list(invoice.obs),
    )


@router.get(
    "/invoices/{invoice_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_invoice_pdf(
    invoice_id: str,
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    renderer: InvoicePdfRenderer = Depends(get_invoice_pdf_renderer),
    _admin: User = Depends(require_admin),
) -> Response:
    invoice = await invoice_repo.get(invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="comprobante_no_encontrado"
        )
    if invoice.estado != ESTADO_APROBADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="comprobante_no_aprobado"
        )
    settings = await invoice_repo.get_settings()
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="invoicing_not_configured",
        )
    pdf = await asyncio.to_thread(
        renderer.render_invoice_arca, invoice_arca_pdf_payload(invoice, settings)
    )
    filename = f"FACTURA_{invoice.punto_venta:04d}-{invoice.numero:08d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/invoicing/settings", response_model=InvoicingSettingsResponse)
async def get_invoicing_settings(
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    _admin: User = Depends(require_admin),
):
    return _settings_response(await invoice_repo.get_settings())


@router.put("/invoicing/settings", response_model=InvoicingSettingsSaved)
async def put_invoicing_settings(
    payload: InvoicingSettingsPayload,
    invoice_repo: SQLInvoiceRepository = Depends(get_invoice_repository),
    _admin: User = Depends(require_admin),
):
    try:
        settings = InvoicingSettings(**payload.model_dump())
    except InvoiceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.code
        ) from None
    await invoice_repo.save_settings(settings)
    return InvoicingSettingsSaved(settings=_settings_payload(settings))

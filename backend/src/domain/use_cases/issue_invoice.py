"""P13 — Emisión de la Factura C de un pedido (RF-P13-01/02/03).

Flujo: pedido → settings del emisor → validaciones fiscales del dominio →
``FECompUltimoAutorizado`` → ``FeCAESolicitar`` → persistencia del
comprobante. El importe es **siempre** el neto del pedido (autoridad del
backend, RNF-P13-06); el payload sólo describe el detalle para el PDF.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from domain.invoicing import (
    CONCEPTO_PRODUCTOS,
    DOC_TIPO_CONSUMIDOR_FINAL,
    ESTADO_APROBADO,
    TIPO_CBTE_FACTURA_C,
    AfipClient,
    AfipWsfeError,
    Invoice,
    InvoiceItem,
    InvoicingNotConfiguredError,
    build_fe_cae_request,
    ensure_order_not_invoiced,
    next_invoice_number,
    normalize_cae,
    sanitize_arca_observaciones,
    validar_fechas_arca,
    validate_concepto_periodo,
    validate_doc_receptor,
    validate_importe,
)

AR_TZ = datetime.timezone(datetime.timedelta(hours=-3))


class OrderNotFoundError(Exception):
    """El pedido a facturar no existe."""

    def __init__(self, order_id: str) -> None:
        self.order_id = order_id
        super().__init__("pedido_no_encontrado")


@dataclass(frozen=True)
class IssueInvoiceRequest:
    """Datos de emisión: concepto, receptor y detalle para el PDF."""

    order_id: str
    concepto: int = CONCEPTO_PRODUCTOS
    doc_tipo: int = DOC_TIPO_CONSUMIDOR_FINAL
    doc_nro: int = 0
    receptor_nombre: str = ""
    fch_serv_desde: datetime.date | None = None
    fch_serv_hasta: datetime.date | None = None
    items: tuple[InvoiceItem, ...] = field(default_factory=tuple)


def _today_ar() -> datetime.date:
    return datetime.datetime.now(AR_TZ).date()


class IssueInvoice:
    def __init__(
        self,
        *,
        invoice_repository,
        order_repository,
        afip_client: AfipClient,
        today: Callable[[], datetime.date] | None = None,
    ) -> None:
        self._invoices = invoice_repository
        self._orders = order_repository
        self._afip = afip_client
        self._today = today or _today_ar

    async def execute(self, request: IssueInvoiceRequest) -> Invoice:
        ensure_order_not_invoiced(await self._invoices.get_by_order(request.order_id))

        order = await self._orders.get(request.order_id)
        if order is None:
            raise OrderNotFoundError(request.order_id)

        settings = await self._invoices.get_settings()
        if settings is None:
            raise InvoicingNotConfiguredError("invoicing_not_configured")

        validate_concepto_periodo(
            request.concepto, request.fch_serv_desde, request.fch_serv_hasta
        )
        validate_doc_receptor(request.doc_tipo, request.doc_nro)

        neto = order.total - (order.discount_amount or Decimal(0))
        total = validate_importe(neto)

        fecha = self._today()
        validar_fechas_arca(
            fecha,
            request.concepto,
            fecha,
            request.fch_serv_desde,
            request.fch_serv_hasta,
        )

        ultimo = await self._afip.last_authorized(
            cuit=settings.cuit,
            punto_venta=settings.punto_venta,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
        )
        numero = next_invoice_number(ultimo)
        payload = build_fe_cae_request(
            punto_venta=settings.punto_venta,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
            numero=numero,
            imp_total=total,
            concepto=request.concepto,
            doc_tipo=request.doc_tipo,
            doc_nro=request.doc_nro,
            fecha=fecha,
            fch_serv_desde=request.fch_serv_desde,
            fch_serv_hasta=request.fch_serv_hasta,
        )

        result = await self._afip.request_cae(cuit=settings.cuit, request=payload)
        observaciones = sanitize_arca_observaciones(result.observaciones)
        cae_vto = result.cae_vto
        if result.resultado != ESTADO_APROBADO or not result.cae or cae_vto is None:
            raise AfipWsfeError("comprobante_rechazado", observaciones)

        invoice = Invoice(
            order_id=request.order_id,
            punto_venta=settings.punto_venta,
            tipo_cbte=TIPO_CBTE_FACTURA_C,
            numero=numero,
            cae=normalize_cae(result.cae),
            cae_vto=cae_vto,
            fecha=fecha,
            imp_total=str(total),
            receptor_doc_tipo=request.doc_tipo,
            receptor_doc_nro=request.doc_nro,
            receptor_nombre=request.receptor_nombre,
            condicion_iva=settings.condicion_iva,
            estado=ESTADO_APROBADO,
            obs=tuple(observaciones),
            items=request.items,
        )
        return await self._invoices.save_invoice(invoice, items=list(request.items))

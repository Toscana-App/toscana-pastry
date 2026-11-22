import hashlib
import json
from abc import ABC, abstractmethod
from decimal import ROUND_HALF_UP, Decimal

from domain.budgets import IVA_PCT, Budget
from domain.invoicing import Invoice, InvoicingSettings


def format_money_peso(amount: Decimal) -> str:
    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    q = abs(q)
    integer, cents = f"{q:.2f}".split(".")
    groups = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    return f"{sign}${'.'.join(groups)},{cents}"


def budget_content_hash(budget: Budget, business_name: str, footer_text: str) -> str:
    totals = budget.totals
    payload = {
        "seq": budget.seq,
        "version": budget.version,
        "customer": {"name": budget.customer_name, "phone": budget.customer_phone},
        "items": [
            {
                "name": item.product_name,
                "qty": item.qty,
                "unit_selling": str(item.unit_selling),
                "line_selling": str(item.line_selling),
            }
            for item in budget.items
        ],
        "subtotal": str(totals.subtotal),
        "iva": str(totals.iva),
        "iva_pct": str(IVA_PCT),
        "total": str(totals.subtotal + totals.iva),
        "brand": {"business_name": business_name, "footer_text": footer_text},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PdfRenderer(ABC):

    @abstractmethod
    def render(self, budget: Budget, business_name: str, footer_text: str) -> bytes:
        pass


class InvoicePdfRenderer(ABC):
    """Borde de render del PDF oficial de un comprobante ARCA (pdfgenerator)."""

    @abstractmethod
    def render_invoice_arca(self, payload: dict) -> bytes:
        pass


def invoice_arca_pdf_payload(invoice: Invoice, settings: InvoicingSettings) -> dict:
    """Payload de ``POST /render/invoice-arca`` (contrato del servicio pdfgenerator).

    Money viaja como string decimal (2 decimales) porque el render formatea el
    documento fiscal; los centavos son la unidad del borde de API propio.
    """
    return {
        "emisor": {
            "cuit": settings.cuit,
            "razon_social": settings.razon_social,
            "domicilio": settings.domicilio,
            "condicion_iva": settings.condicion_iva,
            "categoria_monotributo": settings.categoria_monotributo,
            "ingresos_brutos": settings.ingresos_brutos,
            "inicio_actividades": settings.inicio_actividades,
        },
        "comprobante": {
            "punto_venta": invoice.punto_venta,
            "tipo_cbte": invoice.tipo_cbte,
            "numero": invoice.numero,
            "fecha": invoice.fecha.isoformat(),
            "cae": invoice.cae,
            "cae_vto": invoice.cae_vto.isoformat(),
            "imp_total": invoice.imp_total,
            "receptor": {
                "doc_tipo": invoice.receptor_doc_tipo,
                "doc_nro": invoice.receptor_doc_nro,
                "doc_nombre": invoice.receptor_nombre,
            },
            "items": [
                {
                    "descripcion": item.descripcion,
                    "cantidad": float(item.cantidad),
                    "precio_unit": item.precio_unit,
                }
                for item in invoice.items
            ],
        },
    }

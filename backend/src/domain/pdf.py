"""PDF del presupuesto (Fase 8, P9).

Builder puro: presupuesto de dominio + branding del negocio → bytes de PDF.
ReportLab (A4, Helvetica estándar: sin dependencias de fuentes).

Seguridad (P9): el render solo toca el snapshot del cliente —
productos, cantidades, precios de venta, subtotal, IVA y total —
NUNCA unit_cost, total_costos, ganancia ni margen. La suite de tests
lo garantiza (el texto extraído del PDF no contiene esos términos).

Cache por hash de contenido: `budget_content_hash` se calcula sobre
exactamente lo que se renderiza. Presupuesto editado → hash nuevo →
documento regenerado (invalidación por edición, P9).
"""
import hashlib
import io
import json
from decimal import ROUND_HALF_UP
from decimal import Decimal
from typing import Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from domain.budgets import Budget, IVA_PCT

_MARGIN = 16 * mm
_BRAND = colors.HexColor("#1F3A2D")  # verde oscuro, identidad Toscana
_TEXT = colors.HexColor("#1A1A1A")
_MUTED = colors.HexColor("#5A5A5A")
_GRID = colors.HexColor("#C9C9C9")


def format_money_peso(amount: Decimal) -> str:
    """Dinero en formato es-AR para el documento: $1.550,00
    (punto separador de miles, coma decimales)."""
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


def _format_date(value) -> str:
    """dd/mm/aaaa (es-AR). Acepta datetime con o sin timezone."""
    return value.strftime("%d/%m/%Y")


def budget_content_hash(budget: Budget, business_name: str, footer_text: str) -> str:
    """SHA-256 de exactamente lo que el PDF renderiza (sin costos ni
    margen). Mismo documento → mismo hash; editado cliente, precios o
    branding → hash nuevo (cache invalidada)."""
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
        "iva_pct": str(IVA_PCT),
        "total": str(totals.total_venta),
        "brand": {"business_name": business_name, "footer_text": footer_text},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _styles() -> dict:
    return {
        "business": ParagraphStyle(
            "business", fontName="Helvetica-Bold", fontSize=15,
            leading=19, textColor=_BRAND,
        ),
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=13,
            leading=16, textColor=_TEXT,
        ),
        "meta": ParagraphStyle(
            "meta", fontName="Helvetica", fontSize=9.5,
            leading=13, textColor=_MUTED,
        ),
        "cell": ParagraphStyle(
            "cell", fontName="Helvetica", fontSize=10,
            leading=13, textColor=_TEXT,
        ),
        "cell_bold": ParagraphStyle(
            "cell_bold", fontName="Helvetica-Bold", fontSize=10,
            leading=13, textColor=_TEXT,
        ),
        "header_cell": ParagraphStyle(
            "header_cell", fontName="Helvetica-Bold", fontSize=9.5,
            leading=12, textColor=colors.white,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica-Oblique", fontSize=8.5,
            leading=11, textColor=_MUTED, alignment=TA_CENTER,
        ),
        "total": ParagraphStyle(
            "total", fontName="Helvetica-Bold", fontSize=12,
            leading=15, textColor=_BRAND, alignment=TA_RIGHT,
        ),
    }


def build_budget_pdf(budget: Budget, business_name: str, footer_text: str) -> bytes:
    """Renderiza el presupuesto en PDF (A4).

    Solo el snapshot del cliente (P9): productos, cantidades, precios
    de venta, subtotal, IVA (21%) y total. No aparecen costos, ganancia
    ni margen — ni como dato ni como palabra.
    """
    business = business_name.strip() or "Toscana Pastry"
    totals = budget.totals
    iva_amount = (totals.total_venta - totals.subtotal).quantize(Decimal("0.01"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=f"Presupuesto {budget.seq}",
        author=business,
        subject="Presupuesto",
    )
    s = _styles()
    now = budget.created_at
    fecha = _format_date(now) if now is not None else ""

    elements = [
        Paragraph(business, s["business"]),
        Spacer(1, 2 * mm),
        Table(
            [
                [
                    Paragraph(
                        f"PRESUPUESTO {budget.seq}<br/>"
                        f"Versión {budget.version}<br/>"
                        f"Fecha: {fecha}",
                        s["title"],
                    ),
                    Paragraph(
                        f"<b>Cliente</b><br/>{budget.customer_name}<br/>"
                        f"Tel: {budget.customer_phone}",
                        s["cell"],
                    ),
                ]
            ],
            colWidths=[90 * mm, 142 * mm],
        ),
        Spacer(1, 6 * mm),
    ]

    rows = [
        [
            Paragraph("Producto", s["header_cell"]),
            Paragraph("Cant.", s["header_cell"]),
            Paragraph("Precio unit.", s["header_cell"]),
            Paragraph("Subtotal", s["header_cell"]),
        ]
    ]
    for item in budget.items:
        rows.append(
            [
                Paragraph(item.product_name, s["cell"]),
                Paragraph(str(item.qty), s["cell"]),
                Paragraph(format_money_peso(item.unit_selling), s["cell"]),
                Paragraph(format_money_peso(item.line_selling), s["cell"]),
            ]
        )
    items_table = Table(
        rows,
        colWidths=[98 * mm, 22 * mm, 46 * mm, 66 * mm],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BRAND),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("GRID", (0, 0), (-1, 0), 0.5, _BRAND),
                ("GRID", (0, 1), (-1, -1), 0.5, _GRID),
                ("LINEBELOW", (0, 0), (-1, 0), 1, _BRAND),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 8 * mm))

    total_rows = [
        [Paragraph("Subtotal", s["cell"]), Paragraph(format_money_peso(totals.subtotal), s["cell"])],
        [Paragraph(f"IVA ({IVA_PCT.quantize(Decimal('1'))}%)", s["cell"]), Paragraph(format_money_peso(iva_amount), s["cell"])],
        [Paragraph("Total", s["total"]), Paragraph(format_money_peso(totals.total_venta), s["total"])],
    ]
    totals_table = Table(
        total_rows, colWidths=[60 * mm, 66 * mm], hAlign="RIGHT"
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 1, _BRAND),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(totals_table)
    elements.append(Spacer(1, 14 * mm))

    footer = footer_text.strip() or f"{business} — presupuesto {budget.seq}"
    elements.append(Paragraph(footer, s["footer"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"Presupuesto {budget.seq} · Versión {budget.version} · Documento generado el {fecha}",
        s["footer"],
    ))

    doc.build(elements)
    return buffer.getvalue()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Texto extraído de un PDF (pypdf). Solo para tests: verificar que
    el documento no contiene términos internos (costo/ganancia/margen)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)

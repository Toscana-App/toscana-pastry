"""Render del PDF de presupuesto individual (ReportLab, Platypus).

Movido de ``backend/src/data/pdf/reportlab_renderer.py`` al binario
``pdfgenerator``. Diferencia respecto al original: en vez del objeto de
dominio ``Budget``, recibe un ``BudgetPdfRequest`` plano (DTO por HTTP) para
que el renderer sea autonomo de core-api. El layout es identico: solo se
pinta el snapshot del cliente (nunca costo, ganancia ni margen).
"""
from __future__ import annotations

import io
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..schemas import BudgetPdfRequest

_MARGIN = 16 * mm
_BRAND = colors.HexColor("#1F3A2D")  # verde oscuro, identidad Toscana
_TEXT = colors.HexColor("#1A1A1A")
_MUTED = colors.HexColor("#5A5A5A")
_GRID = colors.HexColor("#C9C9C9")


def _format_date(value: datetime) -> str:
    """dd/mm/aaaa (es-AR). Acepta datetime con o sin timezone."""
    return value.strftime("%d/%m/%Y")


def format_money_peso(amount: Decimal) -> str:
    """Dinero en formato es-AR para el documento: $1.550,00
    (punto separador de miles, coma decimales).

    Movido de ``domain.pdf`` al binario: funcion pura de formateo.
    """
    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    q = abs(q)
    integer, cents = f"{q:.2f}".split(".")
    groups: list[str] = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    return f"{sign}${'.'.join(groups)},{cents}"


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


def build_budget_pdf(req: BudgetPdfRequest) -> bytes:
    """Renderiza el presupuesto (DTO plano) en PDF A4.

    Solo el snapshot del cliente (P9): productos, cantidades, precios de
    venta, subtotal, IVA y total. No aparecen costos, ganancia ni margen —
    ni como dato ni como palabra.
    """
    business = req.business_name.strip() or "Toscana Pastry"
    subtotal = req.subtotal
    iva_amount = req.iva
    total = subtotal + iva_amount

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=f"Presupuesto {req.seq}",
        author=business,
        subject="Presupuesto",
    )
    s = _styles()
    now = req.created_at
    fecha = _format_date(now) if now is not None else ""

    elements = [
        Paragraph(escape(business), s["business"]),
        Spacer(1, 2 * mm),
        Table(
            [
                [
                    Paragraph(
                        f"PRESUPUESTO {req.seq}<br/>"
                        f"Versión {req.version}<br/>"
                        f"Fecha: {fecha}",
                        s["title"],
                    ),
                    Paragraph(
                        f"<b>Cliente</b><br/>{escape(req.customer_name)}<br/>"
                        f"Tel: {escape(req.customer_phone)}"
                        + (
                            f"<br/>Entrega: {escape(req.delivery_address)}"
                            if req.delivery_address
                            else ""
                        ),
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
    for item in req.items:
        rows.append(
            [
                Paragraph(escape(item.product_name), s["cell"]),
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
        [Paragraph("Subtotal", s["cell"]), Paragraph(format_money_peso(subtotal), s["cell"])],
        [Paragraph(f"IVA ({req.iva_pct.quantize(Decimal('1'))}%)", s["cell"]), Paragraph(format_money_peso(iva_amount), s["cell"])],
        [Paragraph("Total", s["total"]), Paragraph(format_money_peso(total), s["total"])],
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

    footer = req.footer_text.strip() or f"{business} — presupuesto {req.seq}"
    elements.append(Paragraph(escape(footer), s["footer"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"Presupuesto {req.seq} · Versión {req.version} · Documento generado el {fecha}",
        s["footer"],
    ))

    doc.build(elements)
    return buffer.getvalue()

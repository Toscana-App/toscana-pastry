"""Render de Factura C ARCA en formato oficial (ReportLab, Canvas).

Endpoint ``POST /render/invoice-arca`` del binario pdfgenerator (decisión D2):
el backend de core-api envía un DTO plano y recibe bytes de PDF. Replica el
layout oficial del comprobante ARCA: banner ORIGINAL, recuadro encabezado
con los datos del EMITENTE y del comprobante, letra "C" destacada, recuadro
RECEPTOR, tabla de detalle y zona de totales con el QR RG 4291/2018 (PNG) y
la URL de verificación bajo el código.

Contrato del payload (JSON, validación estricta — inválido → 422)::

    {
      "emisor": {
        "cuit": "30-12345678-9",        # 11 dígitos, con o sin guiones
        "razon_social": str,
        "domicilio": str,
        "condicion_iva": str,           # ej. "Responsable Monotributo"
        "categoria_monotributo": str,   # "A".."K"
        "ingresos_brutos": str,         # ej. "Exento" o número de inscripción
        "inicio_actividades": str       # ej. "01/03/2024"
      },
      "comprobante": {
        "punto_venta": int,
        "tipo_cbte": 11,                # solo Factura C (monotributo)
        "numero": int,
        "fecha": "YYYY-MM-DD",
        "cae": str,                     # exactamente 14 dígitos
        "cae_vto": "YYYY-MM-DD",
        "imp_total": str,               # decimal 2 decimales, ej. "3100.50"
        "receptor": {
          "doc_tipo": 99 | 80 | 86,     # 99 Consumidor Final / 80 CUIT / 86 DNI
          "doc_nro": int,               # 0 para Consumidor Final
          "doc_nombre": str
        },
        "items": [                      # puede ser vacío
          {"descripcion": str, "cantidad": number>0,
           "precio_unit": str}          # 2 decimales, ej. "3100.50"
        ]
      }
    }

→ ``200 application/pdf`` con
``Content-Disposition: attachment; filename=FACTURA_{punto_venta}-{numero:08d}.pdf``.

QR (RG 4291/2018 / RG 5228/2019): JSON
``{ver, fecha, cuit, ptoVta, tipoCmp, nroCmp, importe, moneda, ctz,
tipoDocRec, nroDocRec, tipoCodAut: "E", codAut}`` → base64 estándar →
URL ``https://www.afip.gob.ar/fe/qr/?p=<base64>`` (funciones puras
``build_qr_payload`` / ``build_qr_url``, testables sin ReportLab).
"""
from __future__ import annotations

import base64
import io
import json
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from xml.sax.saxutils import escape

import qrcode
from pydantic import BaseModel, ConfigDict, Field, field_validator
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

# ── Geometría de la página (A4 retrato) ─────────────────────────────────
# Todos los offsets se expresan en mm desde el borde SUPERIOR; ``_y`` los
# convierte a coordenadas de ReportLab (origen en la esquina inferior izq.).

_PAGE_W, _PAGE_H = A4
_MARGIN = 15 * mm
_CONTENT_W = _PAGE_W - 2 * _MARGIN
_BLACK = colors.black
_WHITE = colors.white
_DARK = colors.Color(0.2, 0.2, 0.2)
_MUTED = colors.HexColor("#5A5A5A")

_BANNER_TOP_MM = 10.0
_BANNER_H_MM = 10.0
_HEADER_TOP_MM = 20.0
_HEADER_H_MM = 52.0
_CBOX_MM = 22.0
_RECEPTOR_TOP_MM = 74.0
_RECEPTOR_H_MM = 16.0
_TABLE_TOP_MM = 92.0
_ROW_H_MM = 6.0
_ROWS_BOTTOM_LIMIT_MM = 240.0  # debajo queda la zona de totales + QR + footer
_CONT_LABEL_MM = 16.0
_CONT_TABLE_TOP_MM = 18.0
_TOTAL_SUBTOTAL_MM = 245.0
_TOTAL_TOTAL_MM = 253.0
_QR_TOP_MM = 243.0
_QR_SIZE_MM = 30.0
_URL_TOP_MM = 275.0
_FOOTER_LINE_MM = 289.0
_FOOTER_TEXT_MM = 294.0

_QR_URL_PREFIX = "https://www.afip.gob.ar/fe/qr/?p="
_QR_ERROR_CORRECTION = ERROR_CORRECT_M


# ── Modelo del payload (contrato completo en el docstring del módulo) ───

_MONEY_RE = re.compile(r"\d+\.\d{2}")
_CAE_RE = re.compile(r"\d{14}")
_CUIT_DIGITS_RE = re.compile(r"\d{11}")
_CUIT_SEP_RE = re.compile(r"\D")
_MONOTRIBUTO_CATEGORIES = "ABCDEFGHIJK"


def normalize_cuit(value: str) -> str:
    """Normaliza un CUIT al formato XX-XXXXXXXX-X.

    Acepta el input con o sin guiones (y otros separadores); valida que
    sean exactamente 11 dígitos.
    """
    digits = _CUIT_SEP_RE.sub("", value)
    if not _CUIT_DIGITS_RE.fullmatch(digits):
        raise ValueError(f"CUIT inválido: {value!r} (se esperan 11 dígitos)")
    return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"


def _validate_money(value: str, field_name: str) -> str:
    if not _MONEY_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} debe ser un decimal con 2 decimales (ej. '3100.50')"
        )
    return value


class EmisorArca(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cuit: str
    razon_social: str
    domicilio: str
    condicion_iva: str
    categoria_monotributo: str
    ingresos_brutos: str
    inicio_actividades: str

    @field_validator("cuit")
    @classmethod
    def _normaliza_cuit(cls, value: str) -> str:
        return normalize_cuit(value)

    @field_validator("categoria_monotributo")
    @classmethod
    def _valida_categoria(cls, value: str) -> str:
        upper = value.upper()
        if len(value) != 1 or upper not in _MONOTRIBUTO_CATEGORIES:
            raise ValueError("categoria_monotributo debe ser una letra entre A y K")
        return upper


class ReceptorArca(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_tipo: Literal[99, 80, 86]
    doc_nro: int = Field(ge=0)
    doc_nombre: str


class ItemArca(BaseModel):
    model_config = ConfigDict(extra="ignore")

    descripcion: str
    cantidad: float = Field(gt=0)
    precio_unit: str

    @field_validator("precio_unit")
    @classmethod
    def _valida_precio(cls, value: str) -> str:
        return _validate_money(value, "precio_unit")


class ComprobanteArca(BaseModel):
    model_config = ConfigDict(extra="ignore")

    punto_venta: int = Field(ge=0)
    tipo_cbte: Literal[11]
    numero: int = Field(ge=0)
    fecha: date
    cae: str
    cae_vto: date
    imp_total: str
    receptor: ReceptorArca
    items: list[ItemArca] = Field(default_factory=list)

    @field_validator("cae")
    @classmethod
    def _valida_cae(cls, value: str) -> str:
        if not _CAE_RE.fullmatch(value):
            raise ValueError("cae debe tener exactamente 14 dígitos")
        return value

    @field_validator("imp_total")
    @classmethod
    def _valida_imp_total(cls, value: str) -> str:
        return _validate_money(value, "imp_total")


class InvoiceArcaRequest(BaseModel):
    """Payload de ``POST /render/invoice-arca`` (contrato en el docstring del módulo)."""

    model_config = ConfigDict(extra="ignore")

    emisor: EmisorArca
    comprobante: ComprobanteArca


# ── QR RG 4291/2018 (funciones puras) ───────────────────────────────────


def build_qr_payload(
    *,
    fecha: date,
    cuit: str,
    punto_venta: int,
    tipo_cbte: int,
    numero: int,
    importe: Decimal,
    doc_tipo: int,
    doc_nro: int,
    cae: str,
) -> dict:
    """Payload JSON del QR del comprobante (RG 4291/2018, RG 5228/2019).

    Claves exactas que exige ARCA para la verificación del comprobante:
    ``ver, fecha, cuit, ptoVta, tipoCmp, nroCmp, importe, moneda, ctz,
    tipoDocRec, nroDocRec, tipoCodAut ("E"), codAut``. ``importe`` queda
    como float con 2 decimales; ``cuit`` sin guiones.
    """
    importe_2dp = float(
        Decimal(str(importe)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    return {
        "ver": 1,
        "fecha": fecha.isoformat(),
        "cuit": _CUIT_SEP_RE.sub("", cuit),
        "ptoVta": punto_venta,
        "tipoCmp": tipo_cbte,
        "nroCmp": numero,
        "importe": importe_2dp,
        "moneda": 0,
        "ctz": 3,
        "tipoDocRec": doc_tipo,
        "nroDocRec": doc_nro,
        "tipoCodAut": "E",
        "codAut": cae,
    }


def build_qr_url(payload: dict) -> str:
    """URL de verificación del QR: base64 estándar del JSON compacto."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return _QR_URL_PREFIX + base64.b64encode(raw).decode("ascii")


# ── Formateo de dinero / cantidades (es-AR) ─────────────────────────────


def format_importe(value: Decimal) -> str:
    """Importe en es-AR sin separador de miles: 3100.50 → ``3100,50``."""
    q = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:.2f}".replace(".", ",")


def format_cantidad(value: float) -> str:
    """Cantidad sin ceros innecesarios: 2.0 → ``2``, 1.5 → ``1,5``."""
    return f"{value:g}".replace(".", ",")


def _wrap(
    text: str, font: str, size: float, max_width: float, max_lines: int = 2
) -> list[str]:
    """Troquea ``text`` en líneas que caben en ``max_width`` puntos."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and stringWidth(last + "…", font, size) > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


# ── Piezas de layout (Canvas, offsets en mm desde arriba) ───────────────


def _y(mm_top: float) -> float:
    """Coordenada y de ReportLab para un punto a ``mm_top`` mm del tope."""
    return _PAGE_H - mm_top * mm


def _paragraph(text: str, bold: bool = False, size: float = 8.0, leading: float | None = None):
    style = ParagraphStyle(
        "invoice_arca",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=leading if leading is not None else size + 2,
        textColor=_BLACK,
    )
    return Paragraph(text, style)


def _draw_banner(c: canvas.Canvas) -> None:
    c.setFillColor(_BLACK)
    c.rect(
        _MARGIN, _y(_BANNER_TOP_MM + _BANNER_H_MM), _CONTENT_W,
        _BANNER_H_MM * mm, fill=1, stroke=0,
    )
    c.setFillColor(_WHITE)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(_PAGE_W / 2, _y(_BANNER_TOP_MM + 7), "ORIGINAL")
    c.setFillColor(_BLACK)


def _draw_header_box(c: canvas.Canvas, em: EmisorArca, cb: ComprobanteArca) -> None:
    y_top = _y(_HEADER_TOP_MM)
    y_bot = _y(_HEADER_TOP_MM + _HEADER_H_MM)
    c.setLineWidth(1)
    c.setFillColor(_WHITE)
    c.rect(_MARGIN, y_bot, _CONTENT_W, _HEADER_H_MM * mm, fill=0, stroke=1)

    cx = _PAGE_W / 2
    c.line(cx, y_top, cx, y_bot)

    # Recuadro de la letra (fondo blanco para tapar la línea central)
    bx = cx - _CBOX_MM * mm / 2
    by = _y(_HEADER_TOP_MM + 1 + _CBOX_MM)
    c.setLineWidth(1.5)
    c.setFillColor(_WHITE)
    c.rect(bx, by, _CBOX_MM * mm, _CBOX_MM * mm, fill=1, stroke=1)
    c.setFillColor(_BLACK)
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(cx, by + 7 * mm, "C")
    c.setFont("Helvetica", 7)
    c.drawCentredString(cx, by + 2 * mm, "COD. 011")

    # Columna izquierda: EMITENTE
    lx = _MARGIN + 4 * mm
    left_width = (cx - 14 * mm) - lx
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(lx, _y(24.0), "EMITENTE")
    emisor_flowables = [
        _paragraph(escape(em.razon_social), bold=True, size=10),
        _paragraph(f"CUIT: <b>{escape(em.cuit)}</b>"),
        _paragraph(f"Domicilio: {escape(em.domicilio)}"),
        _paragraph(f"Ingresos Brutos: {escape(em.ingresos_brutos)}"),
        _paragraph(f"Condición IVA: {escape(em.condicion_iva)}"),
        _paragraph(f"Monotributo: Cat. {escape(em.categoria_monotributo)}"),
        _paragraph(f"Inicio de actividades: {escape(em.inicio_actividades)}"),
    ]
    _stack(c, emisor_flowables, x=lx, width=left_width, y_top_mm=29.5, gap_mm=1.2)

    # Columna derecha: encabezado del comprobante
    rx = cx + 14 * mm
    right_width = _PAGE_W - _MARGIN - 3 * mm - rx
    comprobante_flowables = [
        _paragraph("FACTURA C", bold=True, size=14),
        _paragraph("", size=4),
        _paragraph(f"Punto de venta: <b>{cb.punto_venta:05d}</b>", size=9),
        _paragraph(f"Comprobante: <b>{cb.numero:08d}</b>", size=9),
        _paragraph(f"Fecha de emisión: {_ddmmyyyy(cb.fecha)}", size=8),
        _paragraph(f"CAE N° <b>{escape(cb.cae)}</b>", size=9),
        _paragraph(f"Vto. CAE: {_ddmmyyyy(cb.cae_vto)}", size=8),
    ]
    _stack(c, comprobante_flowables, x=rx, width=right_width, y_top_mm=24.5, gap_mm=1.2)


def _stack(c, flowables, x: float, width: float, y_top_mm: float, gap_mm: float) -> None:
    """Pila flowables abajo de ``y_top_mm`` (ajusta el alto de cada uno)."""
    y = _y(y_top_mm)
    for flowable in flowables:
        _, height = flowable.wrap(width, _PAGE_H)
        if height > 0:
            flowable.drawOn(c, x, y - height)
        y -= height + gap_mm * mm


def _ddmmyyyy(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _draw_receptor_box(c: canvas.Canvas, receptor: ReceptorArca) -> None:
    y_bot = _y(_RECEPTOR_TOP_MM + _RECEPTOR_H_MM)
    c.setLineWidth(0.5)
    c.setFillColor(_WHITE)
    c.rect(
        _MARGIN, y_bot, _CONTENT_W, _RECEPTOR_H_MM * mm, fill=0, stroke=1
    )
    lx = _MARGIN + 4 * mm
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(lx, _y(76.5), "RECEPTOR")
    if receptor.doc_tipo == 99:
        doc_text = "Consumidor Final"
    elif receptor.doc_tipo == 80:
        doc_text = f"CUIT: {receptor.doc_nro}"
    else:
        doc_text = f"DNI: {receptor.doc_nro}"
    c.setFont("Helvetica-Bold", 8)
    c.drawString(lx, _y(81.5), doc_text)
    c.drawString(lx + 45 * mm, _y(81.5), "Apellido y Nombre / Razón Social:")
    c.drawString(lx + 105 * mm, _y(81.5), escape(receptor.doc_nombre))
    if receptor.doc_tipo == 99:
        c.drawString(lx, _y(86.5), "Condición frente al IVA:")
        c.setFont("Helvetica", 8)
        c.drawString(lx + 42 * mm, _y(86.5), "Consumidor Final")


# ── Tabla de detalle ────────────────────────────────────────────────────

_COL2 = _MARGIN + 90 * mm
_COL3 = _COL2 + 20 * mm
_COL4 = _COL3 + 35 * mm
_COL5 = _COL4 + 35 * mm  # == _PAGE_W - _MARGIN


def _draw_table_header(c: canvas.Canvas, top_mm: float) -> None:
    c.setFillColor(_DARK)
    c.rect(
        _MARGIN, _y(top_mm + _ROW_H_MM), _CONTENT_W,
        _ROW_H_MM * mm, fill=1, stroke=0,
    )
    c.setFillColor(_WHITE)
    c.setFont("Helvetica-Bold", 7)
    y = _y(top_mm + _ROW_H_MM - 2.2)
    c.drawString(_MARGIN + 2 * mm, y, "Concepto")
    c.drawRightString(_COL3 - 2 * mm, y, "Cant.")
    c.drawRightString(_COL4 - 2 * mm, y, "Precio unit.")
    c.drawRightString(_COL5 - 2 * mm, y, "Importe")
    c.setFillColor(_BLACK)


def _draw_item_row(c: canvas.Canvas, item: ItemArca, top_mm: float) -> None:
    y = _y(top_mm + _ROW_H_MM - 2.2)
    c.setFont("Helvetica", 7.5)
    descripcion = _wrap(item.descripcion, "Helvetica", 7.5, 86 * mm, max_lines=1)[0]
    c.drawString(_MARGIN + 2 * mm, y, escape(descripcion))
    c.drawRightString(_COL3 - 2 * mm, y, format_cantidad(item.cantidad))
    precio = Decimal(item.precio_unit)
    c.drawRightString(_COL4 - 2 * mm, y, format_importe(precio))
    importe = (precio * Decimal(str(item.cantidad))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    c.drawRightString(_COL5 - 2 * mm, y, format_importe(importe))


def _draw_table_frame(c: canvas.Canvas, top_mm: float, rows: int) -> None:
    bottom = top_mm + _ROW_H_MM + rows * _ROW_H_MM
    c.setLineWidth(0.5)
    c.setFillColor(_WHITE)
    c.rect(_MARGIN, _y(bottom), _CONTENT_W, (bottom - top_mm) * mm, fill=0, stroke=1)
    for x in (_COL2, _COL3, _COL4):
        c.line(x, _y(top_mm), x, _y(bottom))


def _draw_empty_detail(c: canvas.Canvas) -> None:
    c.setLineWidth(0.5)
    c.setFillColor(_WHITE)
    c.rect(_MARGIN, _y(100.0), _CONTENT_W, 8 * mm, fill=0, stroke=1)
    c.setFillColor(_MUTED)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(_PAGE_W / 2, _y(96.8), "Sin detalle de operaciones")
    c.setFillColor(_BLACK)


def _draw_continuation_page(c: canvas.Canvas) -> float:
    """Cabecera de la página de continuación del detalle; devuelve el mm del tope de la primera fila."""
    c.setFont("Helvetica-Bold", 9)
    c.drawString(_MARGIN, _y(_CONT_LABEL_MM), "Detalle de operaciones (continuación)")
    _draw_table_header(c, _CONT_TABLE_TOP_MM)
    return _CONT_TABLE_TOP_MM + _ROW_H_MM


# ── Zona de totales + QR + footer ───────────────────────────────────────


def _qr_payload_for(em: EmisorArca, cb: ComprobanteArca) -> dict:
    return build_qr_payload(
        fecha=cb.fecha,
        cuit=em.cuit,
        punto_venta=cb.punto_venta,
        tipo_cbte=cb.tipo_cbte,
        numero=cb.numero,
        importe=Decimal(cb.imp_total),
        doc_tipo=cb.receptor.doc_tipo,
        doc_nro=cb.receptor.doc_nro,
        cae=cb.cae,
    )


def _qr_image(qr_url: str) -> ImageReader:
    qr = qrcode.QRCode(error_correction=_QR_ERROR_CORRECTION, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_bottom_zone(
    c: canvas.Canvas, em: EmisorArca, cb: ComprobanteArca, qr_url: str
) -> None:
    # Totales (a la izquierda del QR; Factura C: sin IVA aplicado)
    value = f"${format_importe(Decimal(cb.imp_total))}"
    x_val = _PAGE_W - _MARGIN - 36 * mm
    x_lbl = x_val - 52 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(x_lbl, _y(_TOTAL_SUBTOTAL_MM), "Subtotal IVA no aplicado")
    c.setFont("Helvetica", 9)
    c.drawRightString(x_val, _y(_TOTAL_SUBTOTAL_MM), value)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(x_lbl, _y(_TOTAL_TOTAL_MM), "TOTAL")
    c.drawRightString(x_val, _y(_TOTAL_TOTAL_MM), value)

    # QR a la derecha del bloque de totales
    size = _QR_SIZE_MM * mm
    qx = _PAGE_W - _MARGIN - 3 * mm - size
    qy_bottom = _y(_QR_TOP_MM + _QR_SIZE_MM)
    c.drawImage(_qr_image(qr_url), qx, qy_bottom, width=size, height=size)

    # URL de verificación bajo el QR (texto pequeño)
    c.setFont("Helvetica", 4)
    url_mm = _URL_TOP_MM
    for line in _wrap(qr_url, "Helvetica", 4, _CONTENT_W, max_lines=3):
        c.drawString(_MARGIN, _y(url_mm), line)
        url_mm += 2.4

    # Footer: razón social + CUIT
    c.setLineWidth(0.5)
    c.line(_MARGIN, _y(_FOOTER_LINE_MM), _PAGE_W - _MARGIN, _y(_FOOTER_LINE_MM))
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(_MUTED)
    c.drawCentredString(
        _PAGE_W / 2, _y(_FOOTER_TEXT_MM),
        f"{escape(em.razon_social)} — CUIT {escape(em.cuit)}",
    )
    c.setFillColor(_BLACK)


# ── Render principal ────────────────────────────────────────────────────


def render_invoice_arca_pdf(payload: InvoiceArcaRequest) -> bytes:
    """Renderiza la Factura C ARCA (DTO plano) en PDF A4 con QR RG 4291/2018.

    Layout oficial: banner ORIGINAL, recuadro encabezado (EMITENTE |
    comprobante + letra C), recuadro RECEPTOR, tabla de detalle (o bloque
    vacío), totales + QR con URL y footer. El detalle largo pagina; los
    totales y el QR siempre quedan en la última página.
    """
    em = payload.emisor
    cb = payload.comprobante
    qr_url = build_qr_url(_qr_payload_for(em, cb))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Factura C {cb.punto_venta}-{cb.numero:08d}")
    c.setAuthor(em.razon_social)
    c.setSubject("Comprobante fiscal ARCA — Factura C")

    _draw_banner(c)
    _draw_header_box(c, em, cb)
    _draw_receptor_box(c, cb.receptor)

    if not cb.items:
        _draw_table_header(c, _TABLE_TOP_MM)
        _draw_empty_detail(c)
        _draw_bottom_zone(c, em, cb, qr_url)
        c.showPage()
        c.save()
        return buf.getvalue()

    _draw_table_header(c, _TABLE_TOP_MM)
    cursor = _TABLE_TOP_MM + _ROW_H_MM
    table_top = _TABLE_TOP_MM
    rows_on_page = 0
    for item in cb.items:
        if cursor + _ROW_H_MM > _ROWS_BOTTOM_LIMIT_MM:
            _draw_table_frame(c, table_top, rows_on_page)
            c.showPage()
            cursor = _draw_continuation_page(c)
            table_top = _CONT_TABLE_TOP_MM
            rows_on_page = 0
        _draw_item_row(c, item, cursor)
        cursor += _ROW_H_MM
        rows_on_page += 1
    _draw_table_frame(c, table_top, rows_on_page)

    _draw_bottom_zone(c, em, cb, qr_url)
    c.showPage()
    c.save()
    return buf.getvalue()

"""Renderizador de reportes PDF con PyMuPDF (Fase 5).

Patrón "buffer" (artículo oficial de PyMuPDF, 187cae545e9c):

  - ``doc = pymupdf.open()`` → documento NUEVO en memoria (sin archivo;
    para abrir bytes existentes sería ``pymupdf.open(stream=bytes)``).
  - ``page.insert_text(pymupdf.Point(x, y), ...)`` para títulos/footers.
  - ``page.insert_htmlbox(rect, html, css=...)`` para la tabla: el
    PyMuPDF de este entorno (1.28.6) no expone ``Page.insert_table``
    (verificado contra ``dir(Page)``); ``insert_htmlbox`` es la API
    equivalente estable para tablas, con ``doc.new_page()`` extra
    cuando la tabla no cabe (la cabecera se repite en cada página).
  - ``doc.tobytes(garbage=3, deflate=True)`` → ESTO es el buffer:
    ``tobytes()`` es la versión de ``save()`` que guarda en memoria, no
    en disco (garbage=3 + deflate=True recomendados por el artículo).
  - ``doc.close()`` al terminar (o ``with pymupdf.open() as doc:``).

Nunca se escribe un archivo intermedio en disco: el endpoint recibe los
bytes y los sirve directamente en la respuesta HTTP.
"""
from __future__ import annotations

import datetime
import html
from typing import Iterable, List, Sequence

import pymupdf  # PyMuPDF (fitz)

# Geometría A4 en puntos (new_page() por defecto = 595 x 842).
_PAGE_W = 595.0
_MARGIN_X = 40.0
_TOP_Y = 70.0  # baseline del título
_SUBTITLE_Y = 90.0  # baseline del subtítulo
_TABLE_TOP = 112.0
_TABLE_BOTTOM = 778.0
_ROW_HEIGHT = 20.0  # cota conservadora por fila (9pt + padding)
_FOOTER_Y = 808.0

# CSS mínimo para la tabla de insert_htmlbox (bordes + celdas).
_TABLE_CSS = (
    "table { border-collapse: collapse; width: 100%; font-size: 9pt; } "
    "th { text-align: left; border-bottom: 1.5pt solid #333333; "
    "padding: 2pt 4pt; font-weight: bold; } "
    "td { border-bottom: 0.5pt solid #bbbbbb; padding: 2pt 4pt; }"
)


def format_money_cents(cents: int) -> str:
    """Centavos (long de la API) → dinero legible "$1.234,56" (es-AR).

    El wire de la API viaja en centavos (RF-07); los exports lo
    muestran en pesos con separador de miles (punto) y centavos
    (coma), según el requerimiento de export PDF de la Fase 5.
    """
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    pesos, centavos = divmod(c, 100)
    s = f"{pesos:,}".replace(",", ".")
    return f"{sign}${s},{centavos:02d}"


def _page_count_needed(n_rows: int) -> int:
    """Páginas necesarias para n_rows de tabla (1 si no hay filas)."""
    usable = _TABLE_BOTTOM - _TABLE_TOP
    per_page = max(int(usable // _ROW_HEIGHT), 1)
    return max(1, (n_rows + per_page - 1) // per_page)


def _table_html(columns: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """HTML de la tabla (cabecera + filas), con celdas escapadas."""
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_report_pdf(
    title: str,
    subtitle: str,
    columns: Sequence[str],
    rows: List[List[str]],
    footer: str = "",
) -> bytes:
    """Renderiza un reporte genérico (título + tabla + footer) y
    devuelve los bytes del PDF.

    - ``columns``: cabecera (una fila, estilo header).
    - ``rows``: filas de datos (todas con ``len(columns)`` celdas str).
    - Paginación automática: si la tabla no cabe en la página A4 se
      abre una página nueva y se repite la cabecera.

    El documento se construye ENTERAMENTE en memoria (patrón buffer)
    y se serializa con ``tobytes(garbage=3, deflate=True)``.
    """
    if not columns:
        raise ValueError("columns no puede estar vacio")

    doc = pymupdf.open()  # documento NUEVO en memoria (sin archivo)
    body_rows = [list(r) for r in rows]
    n_pages = _page_count_needed(len(body_rows))
    per_page = max(int((_TABLE_BOTTOM - _TABLE_TOP) // _ROW_HEIGHT), 1)

    for i in range(n_pages):
        page = doc.new_page()  # A4 por defecto
        page.insert_text(pymupdf.Point(_MARGIN_X, _TOP_Y), title, fontsize=16)
        suffix = "" if i == 0 else " (continuación)"
        if subtitle:
            page.insert_text(
                pymupdf.Point(_MARGIN_X, _SUBTITLE_Y),
                subtitle + suffix,
                fontsize=10,
            )
        chunk = body_rows[i * per_page:(i + 1) * per_page]
        rect = pymupdf.Rect(
            _MARGIN_X,
            _TABLE_TOP,
            _PAGE_W - _MARGIN_X,
            _TABLE_BOTTOM,
        )
        # La cabecera (thead) se repite en cada página.
        page.insert_htmlbox(rect, _table_html(columns, chunk), css=_TABLE_CSS)

    if footer:
        last = doc[-1]
        last.insert_text(pymupdf.Point(_MARGIN_X, _FOOTER_Y), footer, fontsize=8)

    # Buffer: serializa en memoria (versión de save() sin disco).
    pdf_bytes = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return pdf_bytes


# ─── Wrappers específicos (formatean dinero y fechas) ────────────────


def render_weekly_pdf(
    monday: datetime.date,
    sunday: datetime.date,
    orders: Iterable[tuple[datetime.date, str, int, int, bool, str]],
    total_cents: int,
    paid_cents: int,
) -> bytes:
    """PDF del resumen semanal (RF-P6-11).

    ``orders``: tuplas ``(fecha, cliente, items_count, total_cents,
    paid, metodo)``. Los totales van en el footer (monto total, pagado
    y pendiente), formateados en pesos.
    """
    # orders puede ser un iterable; lo materializo una sola vez para
    # contar las filas del subtitle y armar la tabla.
    orders = list(orders)
    subtitle = (
        f"Semana del {monday.strftime('%d/%m/%Y')} al {sunday.strftime('%d/%m/%Y')}"
        f" - {len(orders)} pedidos"
    )
    columns = ["Fecha", "Cliente", "Items", "Total", "Pago", "Metodo"]
    rows = [
        [
            d.strftime("%d/%m/%Y"),
            cliente,
            str(n_items),
            format_money_cents(cents),
            "Pagado" if paid else "Pendiente",
            metodo,
        ]
        for d, cliente, n_items, cents, paid, metodo in orders
    ]
    pending_cents = total_cents - paid_cents
    footer = (
        "Totales: "
        f"{format_money_cents(total_cents)} | "
        f"Pagado: {format_money_cents(paid_cents)} | "
        f"Pendiente: {format_money_cents(pending_cents)}"
    )
    return render_report_pdf(
        title="Resumen semanal de pedidos",
        subtitle=subtitle,
        columns=columns,
        rows=rows,
        footer=footer,
    )


def render_orders_export_pdf(
    period_label: str,
    orders: Iterable[tuple[str, str, datetime.date, int, int, str, bool, str]],
) -> bytes:
    """PDF del export de pedidos (mismo contenido que el CSV).

    ``orders``: tuplas ``(id, cliente, fecha, items_count, total_cents,
    estado, paid, metodo)``.
    """
    orders = list(orders)
    columns = ["ID", "Cliente", "Fecha", "Items", "Total", "Estado", "Pago", "Metodo"]
    rows = [
        [
            oid or "",
            cliente,
            fecha.strftime("%d/%m/%Y"),
            str(n_items),
            format_money_cents(cents),
            estado,
            "si" if paid else "no",
            metodo,
        ]
        for oid, cliente, fecha, n_items, cents, estado, paid, metodo in orders
    ]
    return render_report_pdf(
        title="Export de pedidos",
        subtitle=f"Periodo: {period_label} - {len(orders)} pedidos",
        columns=columns,
        rows=rows,
        footer="Generado por Toscana Pastry — export de pedidos (Fase 5)",
    )


def render_budgets_export_pdf(
    period_label: str,
    budgets: Iterable[tuple[str, str, str, datetime.date, datetime.date | None, str, int]],
) -> bytes:
    """PDF del export de presupuestos (mismo contenido que el CSV).

    ``budgets``: tuplas ``(seq, cliente, telefono, fecha, enviado,
    estado, total_venta_cents)``.
    """
    budgets = list(budgets)
    columns = [
        "Secuencia", "Cliente", "Telefono", "Fecha", "Enviado", "Estado",
        "Total venta",
    ]
    rows = [
        [
            f"#{seq}",
            cliente,
            telefono,
            fecha.strftime("%d/%m/%Y"),
            enviado.strftime("%d/%m/%Y") if enviado else "",
            estado,
            format_money_cents(total_cents),
        ]
        for seq, cliente, telefono, fecha, enviado, estado, total_cents in budgets
    ]
    return render_report_pdf(
        title="Export de presupuestos",
        subtitle=f"Periodo: {period_label} - {len(budgets)} presupuestos",
        columns=columns,
        rows=rows,
        footer="Generado por Toscana Pastry — export de presupuestos (Fase 5)",
    )

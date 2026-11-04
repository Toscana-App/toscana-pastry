"""Tests de UNIDAD del renderer PDF con PyMuPDF (Fase 5).

Estos tests SÍ se ejecutan en el entorno sin Postgres: el renderer no
toca la base de datos (solo bytes en memoria, patrón "buffer").

Cobertura:
- format_money_cents (centavos → $X.XXX,XX es-AR).
- render_report_pdf genérico: magic bytes %PDF, re-open con
  ``pymupdf.open(stream=bytes)``, page_count, extracción de texto
  (título, cliente, monto), paginación con repetición de cabecera.
- Wrappers específicos: resumen semanal, export pedidos, export
  presupuestos.
"""
import datetime

import pymupdf
import pytest

from data.pdf_export.pymupdf_renderer import (
    format_money_cents,
    render_budgets_export_pdf,
    render_orders_export_pdf,
    render_report_pdf,
    render_weekly_pdf,
)


# ─── format_money_cents ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "$0,00"),
        (5, "$0,05"),
        (100, "$1,00"),
        (1234567, "$12.345,67"),
        (810050, "$8.100,50"),
        (-1234567, "-$12.345,67"),
    ],
)
def test_format_money_cents(cents, expected):
    assert format_money_cents(cents) == expected


# ─── render_report_pdf (genérico) ────────────────────────────────────

COLUMNS = ["Fecha", "Cliente", "Items", "Total", "Pago", "Metodo"]
ROWS = [
    ["02/11/2026", "Juan Pérez", "3", "$12.345,67", "Pagado", "efectivo"],
    ["03/11/2026", "María Gómez", "1", "$800,00", "Pendiente", "mp"],
]


def _open(pdf_bytes: bytes) -> pymupdf.Document:
    """Reabre los bytes en memoria (verifica que el buffer es un PDF
    válido y que no se dependió de ningún archivo intermedio)."""
    return pymupdf.open(stream=pdf_bytes)


def _text_of(doc: pymupdf.Document, page: int | None = None) -> str:
    """Texto extraído normalizando las ligaduras tipográficas.

    insert_htmlbox renderiza con la fuente Fira Sans integrada, que
    liga "fi" (U+FB01): visualmente correcto, pero get_text() extrae
    la ligadura en vez de "fi". Para los asserts se normaliza.
    """
    raw = doc[page].get_text() if page is not None else "".join(p.get_text() for p in doc)
    return raw.replace("\ufb01", "fi")


def test_render_report_pdf_bytes_and_text():
    pdf_bytes = render_report_pdf(
        title="Resumen semanal de pedidos",
        subtitle="Semana del 02/11/2026 al 08/11/2026 — 2 pedidos",
        columns=COLUMNS,
        rows=ROWS,
        footer="Totales: $13.145,67 | Pagado: $12.345,67 | Pendiente: $800,00",
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF"), "los bytes deben ser un PDF válido"

    doc = _open(pdf_bytes)
    assert doc.page_count >= 1
    text = _text_of(doc, 0)
    # Título, subtítulo, cabecera, una fila (cliente + monto) y footer.
    assert "Resumen semanal de pedidos" in text
    assert "02/11/2026 al 08/11/2026" in text
    assert "Cliente" in text
    assert "Juan Pérez" in text
    assert "$12.345,67" in text
    assert "Pendiente" in text
    assert "Totales: $13.145,67" in text
    doc.close()


def test_render_report_pdf_empty_rows_single_page():
    """Sin filas de datos: una sola página con solo la cabecera."""
    pdf_bytes = render_report_pdf(
        title="Export de pedidos",
        subtitle="Periodo: todos — 0 pedidos",
        columns=COLUMNS,
        rows=[],
        footer="sin datos",
    )
    doc = _open(pdf_bytes)
    assert doc.page_count == 1
    assert "Export de pedidos" in _text_of(doc, 0)
    doc.close()


def test_render_report_pdf_multipage_repeats_header():
    """Tabla larga: paginación A4 + repetición de la cabecera."""
    rows = [
        [f"02/11/2026", f"Cliente {i:02d}", "1", "$1.000,00", "Pagado", "efectivo"]
        for i in range(120)
    ]
    pdf_bytes = render_report_pdf(
        title="Reporte largo",
        subtitle="120 filas",
        columns=COLUMNS,
        rows=rows,
        footer="fin",
    )
    doc = _open(pdf_bytes)
    assert doc.page_count > 1
    # La cabecera se repite en la segunda página.
    assert "Cliente" in _text_of(doc, 1)
    assert "Cliente 40" in _text_of(doc, 1) or "Cliente 60" in _text_of(doc, 1)
    # La última fila cae en la última página.
    assert "Cliente 119" in _text_of(doc, -1)
    doc.close()


def test_render_report_pdf_requires_columns():
    with pytest.raises(ValueError):
        render_report_pdf(title="t", subtitle="", columns=[], rows=[])


# ─── Wrappers específicos ────────────────────────────────────────────


def test_render_weekly_pdf():
    monday = datetime.date(2026, 11, 2)
    sunday = datetime.date(2026, 11, 8)
    orders = [
        (monday, "Juan Pérez", 3, 1234567, True, "efectivo"),
        (monday + datetime.timedelta(days=1), "María Gómez", 1, 80000, False, "mp"),
    ]
    pdf_bytes = render_weekly_pdf(monday, sunday, orders, 1314567, 1234567)
    assert pdf_bytes.startswith(b"%PDF")
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "Resumen semanal de pedidos" in text
    assert "Semana del 02/11/2026 al 08/11/2026 - 2 pedidos" in text
    assert "Juan Pérez" in text
    assert "$12.345,67" in text
    assert "Pagado" in text
    assert "Pendiente" in text
    # Footer con totales formateados.
    full_text = _text_of(doc)
    assert "Totales: $13.145,67" in full_text
    assert "Pagado: $12.345,67" in full_text
    assert "Pendiente: $800,00" in full_text
    doc.close()


def test_render_weekly_pdf_accepts_iterator():
    """orders como iterable (no lista): se materializa una sola vez."""
    monday = datetime.date(2026, 11, 2)
    sunday = datetime.date(2026, 11, 8)
    gen = iter([(monday, "Solo Uno", 1, 10050, True, "efectivo")])
    pdf_bytes = render_weekly_pdf(monday, sunday, gen, 10050, 10050)
    doc = _open(pdf_bytes)
    assert "Solo Uno" in _text_of(doc, 0)
    doc.close()


def test_render_orders_export_pdf():
    orders = [
        ("o-1", "Juan Pérez", datetime.date(2026, 11, 2), 3, 1234567,
         "confirmado", True, "efectivo"),
    ]
    pdf_bytes = render_orders_export_pdf("2026-11-02 a 2026-11-08", orders)
    assert pdf_bytes.startswith(b"%PDF")
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "Export de pedidos" in text
    assert "o-1" in text
    assert "Juan Pérez" in text
    assert "$12.345,67" in text
    assert "confirmado" in text
    doc.close()


def test_render_budgets_export_pdf():
    budgets = [
        ("00042", "María Gómez", "+54 9 11 5555-0100",
         datetime.date(2026, 11, 1), datetime.date(2026, 11, 1),
         "enviado", 452000),
    ]
    pdf_bytes = render_budgets_export_pdf("todos", budgets)
    assert pdf_bytes.startswith(b"%PDF")
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "Export de presupuestos" in text
    assert "#00042" in text
    assert "María Gómez" in text
    assert "$4.520,00" in text
    assert "enviado" in text
    doc.close()

import datetime

import pymupdf
import pytest

from pdfgenerator.renderers import (
    format_money_cents,
    render_budgets_export_pdf,
    render_orders_export_pdf,
    render_report_pdf,
    render_weekly_pdf,
)


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


COLUMNS = ["Fecha", "Cliente", "Ítems", "Total", "Pago", "Método"]
ROWS = [
    ["02/11/2026", "Juan Pérez", "3", "$12.345,67", "Pagado", "efectivo"],
    ["03/11/2026", "María Gómez", "1", "$800,00", "Pendiente", "mp"],
]


def _open(pdf_bytes: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=pdf_bytes)


def _text_of(doc: pymupdf.Document, page: int | None = None) -> str:
    raw = doc[page].get_text() if page is not None else "".join(p.get_text() for p in doc)
    return raw.replace("\ufb01", "fi")


def test_render_report_pdf_bytes_and_text():
    pdf_bytes = render_report_pdf(
        title="Resumen semanal de pedidos",
        subtitle="Semana del 02/11/2026 al 08/11/2026 - 2 pedidos",
        columns=COLUMNS,
        rows=ROWS,
        footer="Totales: $13.145,67 | Pagado: $12.345,67 | Pendiente: $800,00",
        business_name="Toscana Pastry",
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    doc = _open(pdf_bytes)
    assert doc.page_count >= 1
    text = _text_of(doc, 0)
    assert "Toscana Pastry" in text
    assert "Resumen semanal de pedidos" in text
    assert "02/11/2026 al 08/11/2026" in text
    # El header "Cliente" se renderiza en mayúsculas (text-transform).
    assert "cliente" in text.lower()
    assert "Juan Pérez" in text
    assert "$12.345,67" in text
    assert "Pendiente" in text
    assert "Totales: $13.145,67" in text
    doc.close()


def test_render_report_pdf_empty_rows_single_page():
    pdf_bytes = render_report_pdf(
        title="Export de pedidos",
        subtitle="Período: todos - 0 pedidos",
        columns=COLUMNS,
        rows=[],
        footer="sin datos",
    )
    doc = _open(pdf_bytes)
    assert doc.page_count == 1
    text = _text_of(doc, 0)
    assert "Export de pedidos" in text
    assert "Sin registros en el período." in text
    assert "sin datos" in text
    doc.close()


def test_render_report_pdf_multipage_repeats_header():
    rows = [
        ["02/11/2026", f"Cliente {i:02d}", "1", "$1.000,00", "Pagado", "efectivo"]
        for i in range(120)
    ]
    pdf_bytes = render_report_pdf(
        title="Reporte largo", subtitle="120 filas", columns=COLUMNS, rows=rows, footer="fin"
    )
    doc = _open(pdf_bytes)
    assert doc.page_count > 1
    # El thead se repite en cada página; el header va en mayúsculas.
    assert "CLIENTE" in _text_of(doc, 1)
    assert "Cliente 119" in _text_of(doc, -1)
    assert "Página 1 de" in _text_of(doc, 0)
    doc.close()


def test_render_report_pdf_requires_columns():
    with pytest.raises(ValueError):
        render_report_pdf(title="t", subtitle="", columns=[], rows=[])


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
    full_text = _text_of(doc)
    assert "Cobrado" in full_text
    assert "$13.145,67" in full_text
    assert "$800,00" in full_text
    assert "TOTAL FACTURADO" in full_text
    doc.close()


def test_render_weekly_pdf_accepts_iterator():
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
    assert "Confirmado" in text
    assert "02/11/2026 a 08/11/2026" in text
    doc.close()


def test_render_orders_export_pdf_sums_paid_and_pending():
    orders = [
        ("o-1", "Juan Pérez", datetime.date(2026, 11, 2), 3, 100000,
         "confirmado", True, "efectivo"),
        ("o-2", "María Gómez", datetime.date(2026, 11, 3), 1, 50000,
         "nuevo", False, "mp"),
    ]
    pdf_bytes = render_orders_export_pdf("todos", orders)
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "$1.000,00" in text
    assert "$500,00" in text
    assert "$1.500,00" in text
    doc.close()


def test_render_orders_export_pdf_escapes_client_name():
    orders = [
        ("o-1", "<script>alert(1)</script>", datetime.date(2026, 11, 2), 1, 100,
         "nuevo", False, "mp"),
    ]
    pdf_bytes = render_orders_export_pdf("todos", orders)
    doc = _open(pdf_bytes)
    assert "<script>" in _text_of(doc, 0)
    doc.close()


def test_render_orders_export_pdf_uses_settings_identity():
    orders = [
        ("o-1", "Juan Pérez", datetime.date(2026, 11, 2), 1, 100, "nuevo", False, "mp"),
    ]
    pdf_bytes = render_orders_export_pdf(
        "todos", orders, "Pastelería del Sur", "Devoluciones dentro de 48 horas."
    )
    doc = _open(pdf_bytes)
    full_text = _text_of(doc)
    assert "Pastelería del Sur" in full_text
    assert "Devoluciones dentro de 48 horas." in full_text
    doc.close()


def test_render_budgets_export_pdf():
    budgets = [
        ("00042", "María Gómez", "+54 9 11 5555-0100",
         datetime.date(2026, 11, 1), datetime.date(2026, 11, 1),
         "enviado", 452000, 94920),
    ]
    pdf_bytes = render_budgets_export_pdf("todos", budgets)
    assert pdf_bytes.startswith(b"%PDF")
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "Export de presupuestos" in text
    assert "#00042" in text
    assert "María Gómez" in text
    assert "$4.520,00" in text
    assert "Enviado" in text
    doc.close()


def test_render_budgets_export_pdf_empty_has_no_totals():
    pdf_bytes = render_budgets_export_pdf("todos", [])
    doc = _open(pdf_bytes)
    text = _text_of(doc, 0)
    assert "No hay presupuestos para el período seleccionado." in text
    # Sin filas no se renderiza el bloque de totales (los headers de columna sí).
    assert "Neto" not in text
    assert "$0,00" not in text
    doc.close()

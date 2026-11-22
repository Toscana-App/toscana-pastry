from __future__ import annotations

import datetime
import re
from typing import Iterable, List, Sequence

from .document import render_document_pdf

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _human_period(label: str) -> str:
    return _ISO_DATE.sub(r"\3/\2/\1", label)


def format_money_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    pesos, centavos = divmod(c, 100)
    s = f"{pesos:,}".replace(",", ".")
    return f"{sign}${s},{centavos:02d}"


def render_report_pdf(
    title: str,
    subtitle: str,
    columns: Sequence[str],
    rows: List[List[str]],
    footer: str = "",
    business_name: str = "",
    footer_text: str = "",
    numeric_columns: Sequence[int] = (),
    pill_columns: Sequence[int] = (),
    meta: Sequence[tuple[str, str]] = (),
    totals: Sequence[tuple[str, str]] = (),
    column_widths: Sequence[str] = (),
    document_kind: str = "Documento de gestión",
    badge: str = "",
    section_title: str = "Detalle",
    empty_message: str = "Sin registros en el período.",
) -> bytes:
    if not columns:
        raise ValueError("columns no puede estar vacio")
    return render_document_pdf(
        title=title,
        subtitle=subtitle,
        business_name=business_name,
        footer_text=footer_text or footer,
        document_kind=document_kind,
        badge=badge,
        meta=meta,
        columns=columns,
        rows=rows,
        numeric_columns=numeric_columns,
        pill_columns=pill_columns,
        totals=totals,
        section_title=section_title,
        empty_message=empty_message,
        column_widths=column_widths,
    )


def render_weekly_pdf(
    monday: datetime.date,
    sunday: datetime.date,
    orders: Iterable[tuple[datetime.date, str, int, int, bool, str]],
    total_cents: int,
    paid_cents: int,
    business_name: str = "",
    footer_text: str = "",
) -> bytes:
    orders = list(orders)
    pending_cents = total_cents - paid_cents
    period = f"{monday.strftime('%d/%m/%Y')} al {sunday.strftime('%d/%m/%Y')}"
    subtitle = f"Semana del {period} - {len(orders)} pedidos"
    columns = ["Fecha", "Cliente", "Ítems", "Total", "Pago", "Método"]
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
    meta = [
        ("Período", period),
        ("Pedidos", str(len(orders))),
        ("Ítems", str(sum(o[2] for o in orders))),
        ("Clientes", str(len({o[1] for o in orders}))),
    ]
    totals = [
        ("Cobrado", format_money_cents(paid_cents)),
        ("Pendiente", format_money_cents(pending_cents)),
        ("Total facturado", format_money_cents(total_cents)),
    ]
    return render_report_pdf(
        title="Resumen semanal de pedidos",
        subtitle=subtitle,
        columns=columns,
        rows=rows,
        footer=footer_text or "Resumen generado por Toscana Pastry.",
        business_name=business_name,
        footer_text=footer_text,
        numeric_columns=(2, 3),
        column_widths=("12%", "31%", "8%", "16%", "15%", "18%"),
        meta=meta,
        totals=totals,
        document_kind="Resumen operativo",
        section_title="Pedidos de la semana",
        empty_message="No hay pedidos registrados en esta semana.",
    )


def render_orders_export_pdf(
    period_label: str,
    orders: Iterable[tuple[str, str, datetime.date, int, int, str, bool, str]],
    business_name: str = "",
    footer_text: str = "",
) -> bytes:
    orders = list(orders)
    total_cents = sum(o[4] for o in orders)
    paid_cents = sum(o[4] for o in orders if o[6])
    pending_cents = total_cents - paid_cents
    columns = ["ID", "Cliente", "Fecha", "Ítems", "Total", "Estado", "Pago", "Método"]
    rows = [
        [
            oid or "",
            cliente,
            fecha.strftime("%d/%m/%Y"),
            str(n_items),
            format_money_cents(cents),
            estado,
            "Sí" if paid else "No",
            metodo,
        ]
        for oid, cliente, fecha, n_items, cents, estado, paid, metodo in orders
    ]
    meta = [
        ("Período", _human_period(period_label)),
        ("Pedidos", str(len(orders))),
        ("Ítems", str(sum(o[3] for o in orders))),
        ("Clientes", str(len({o[1] for o in orders}))),
    ]
    totals = [
        ("Cobrado", format_money_cents(paid_cents)),
        ("Pendiente de cobro", format_money_cents(pending_cents)),
        ("Total facturado", format_money_cents(total_cents)),
    ]
    return render_report_pdf(
        title="Export de pedidos",
        subtitle=f"Período: {_human_period(period_label)} - {len(orders)} pedidos",
        columns=columns,
        rows=rows,
        footer=footer_text or "Generado por Toscana Pastry · export de pedidos.",
        business_name=business_name,
        footer_text=footer_text,
        numeric_columns=(3, 4),
        pill_columns=(5,),
        column_widths=("8%", "22%", "11%", "8%", "13%", "16%", "7%", "15%"),
        meta=meta,
        totals=totals,
        document_kind="Comprobante de gestión",
        section_title="Pedidos del período",
        empty_message="No hay pedidos para el período seleccionado.",
    )


def render_budgets_export_pdf(
    period_label: str,
    budgets: Iterable[tuple[str, str, str, datetime.date, datetime.date | None, str, int, int]],
    business_name: str = "",
    footer_text: str = "",
) -> bytes:
    budgets = list(budgets)
    total_cents = sum(b[6] for b in budgets)
    iva_cents = sum(b[7] for b in budgets)
    net_cents = total_cents - iva_cents
    columns = [
        "Secuencia", "Cliente", "Teléfono", "Fecha", "Enviado", "Estado",
        "Total venta", "IVA",
    ]
    rows = [
        [
            f"#{seq}",
            cliente,
            telefono,
            fecha.strftime("%d/%m/%Y"),
            enviado.strftime("%d/%m/%Y") if enviado else "—",
            estado,
            format_money_cents(total_cents_row),
            format_money_cents(iva_row),
        ]
        for seq, cliente, telefono, fecha, enviado, estado, total_cents_row, iva_row in budgets
    ]
    meta = [
        ("Período", _human_period(period_label)),
        ("Presupuestos", str(len(budgets))),
        ("Enviados", str(sum(1 for b in budgets if b[4] is not None))),
        ("Sin enviar", str(sum(1 for b in budgets if b[4] is None))),
    ]
    totals = [
        ("Neto", format_money_cents(net_cents)),
        ("IVA", format_money_cents(iva_cents)),
        ("Total venta", format_money_cents(total_cents)),
    ]
    return render_report_pdf(
        title="Export de presupuestos",
        subtitle=f"Período: {_human_period(period_label)} - {len(budgets)} presupuestos",
        columns=columns,
        rows=rows,
        footer=footer_text or "Generado por Toscana Pastry · export de presupuestos.",
        business_name=business_name,
        footer_text=footer_text,
        numeric_columns=(6, 7),
        pill_columns=(5,),
        column_widths=("11%", "16%", "21%", "11%", "11%", "11%", "10%", "9%"),
        meta=meta,
        totals=totals,
        document_kind="Comprobante de gestión",
        section_title="Presupuestos del período",
        empty_message="No hay presupuestos para el período seleccionado.",
    )

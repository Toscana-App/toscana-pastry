"""Renderers del binario pdfgenerator (PyMuPDF, ReportLab, WeasyPrint)."""
from .budget import build_budget_pdf, format_money_peso
from .invoice_arca import (
    InvoiceArcaRequest,
    build_qr_payload,
    build_qr_url,
    normalize_cuit,
    render_invoice_arca_pdf,
)
from .pricelist import render_pricelist
from .report import (
    format_money_cents,
    render_budgets_export_pdf,
    render_orders_export_pdf,
    render_report_pdf,
    render_weekly_pdf,
)

__all__ = [
    "InvoiceArcaRequest",
    "build_budget_pdf",
    "build_qr_payload",
    "build_qr_url",
    "format_money_cents",
    "format_money_peso",
    "normalize_cuit",
    "render_budgets_export_pdf",
    "render_invoice_arca_pdf",
    "render_orders_export_pdf",
    "render_pricelist",
    "render_report_pdf",
    "render_weekly_pdf",
]

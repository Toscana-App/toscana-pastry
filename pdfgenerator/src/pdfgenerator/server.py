"""App FastAPI del binario pdfgenerator + entrypoint.

Cada endpoint de ``/render/*`` recibe un DTO plano (JSON) y devuelve bytes de
PDF (``application/pdf``). El render es CPU-bound (PyMuPDF/ReportLab/
WeasyPrint) y corre en el threadpool para no bloquear el event loop.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import Response

from . import __version__
from .renderers import (
    build_budget_pdf,
    render_budgets_export_pdf,
    render_orders_export_pdf,
    render_pricelist,
    render_weekly_pdf,
)
from .schemas import (
    BudgetPdfRequest,
    BudgetsExportRequest,
    OrdersExportRequest,
    PricelistRequest,
    WeeklyRequest,
)

PDF_RESPONSE = "application/pdf"


def create_app() -> FastAPI:
    app = FastAPI(title="pdfgenerator", version=__version__)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "service": "pdfgenerator", "version": __version__}

    @app.post("/render/pricelist")
    async def render_pricelist_endpoint(req: PricelistRequest) -> Response:
        pdf = await asyncio.to_thread(render_pricelist, req.rows, req.audience_label)
        return Response(content=pdf, media_type=PDF_RESPONSE)

    @app.post("/render/weekly")
    async def render_weekly_endpoint(req: WeeklyRequest) -> Response:
        orders = [
            (o.fecha, o.cliente, o.items, o.total_cents, o.paid, o.metodo)
            for o in req.orders
        ]
        pdf = await asyncio.to_thread(
            render_weekly_pdf,
            req.monday,
            req.sunday,
            orders,
            req.total_cents,
            req.paid_cents,
        )
        return Response(content=pdf, media_type=PDF_RESPONSE)

    @app.post("/render/orders-export")
    async def render_orders_export_endpoint(req: OrdersExportRequest) -> Response:
        orders = [
            (o.id, o.cliente, o.fecha, o.items, o.total_cents, o.estado, o.paid, o.metodo)
            for o in req.orders
        ]
        pdf = await asyncio.to_thread(
            render_orders_export_pdf, req.period_label, orders
        )
        return Response(content=pdf, media_type=PDF_RESPONSE)

    @app.post("/render/budgets-export")
    async def render_budgets_export_endpoint(req: BudgetsExportRequest) -> Response:
        budgets = [
            (b.seq, b.cliente, b.telefono, b.fecha, b.enviado, b.estado, b.total_cents)
            for b in req.budgets
        ]
        pdf = await asyncio.to_thread(
            render_budgets_export_pdf, req.period_label, budgets
        )
        return Response(content=pdf, media_type=PDF_RESPONSE)

    @app.post("/render/budget")
    async def render_budget_endpoint(req: BudgetPdfRequest) -> Response:
        pdf = await asyncio.to_thread(build_budget_pdf, req)
        return Response(content=pdf, media_type=PDF_RESPONSE)

    return app


app = create_app()


def run() -> None:
    """Entrypoint del binario ``pdfgenerator`` (``[project.scripts]``)."""
    import uvicorn

    host = os.environ.get("PDFGEN_HOST", "127.0.0.1")
    port = int(os.environ.get("PDFGEN_PORT", "8100"))
    uvicorn.run(app, host=host, port=port, log_level="info")

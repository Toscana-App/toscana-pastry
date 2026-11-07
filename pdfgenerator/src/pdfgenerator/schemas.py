"""DTOs de request del binario pdfgenerator.

Todo lo que entra por HTTP es datos planos: sin dependencia del dominio de
core-api. El presupuesto llega como un ``BudgetPdfRequest`` plano (ya no el
objeto ``Budget``) para que el renderer ReportLab sea autonomo.

Money entra como ``Decimal`` (Pydantic v2 lo parsea de string/number JSON con
precision exacta).
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ─── Pricelist (WeasyPrint) ───────────────────────────────────────────


class PricelistRow(BaseModel):
    name: str
    unit: str
    price: str  # ya formateado ("$1.234,56"); el caller lo arma


class PricelistRequest(BaseModel):
    audience_label: str = "Todos"
    rows: list[PricelistRow] = Field(default_factory=list)


# ─── Weekly / orders / budgets export (PyMuPDF) ───────────────────────


class WeeklyOrderRow(BaseModel):
    fecha: datetime.date
    cliente: str
    items: int
    total_cents: int
    paid: bool
    metodo: str


class WeeklyRequest(BaseModel):
    monday: datetime.date
    sunday: datetime.date
    orders: list[WeeklyOrderRow] = Field(default_factory=list)
    total_cents: int
    paid_cents: int


class OrdersExportRow(BaseModel):
    id: str
    cliente: str
    fecha: datetime.date
    items: int
    total_cents: int
    estado: str
    paid: bool
    metodo: str


class OrdersExportRequest(BaseModel):
    period_label: str
    orders: list[OrdersExportRow] = Field(default_factory=list)


class BudgetsExportRow(BaseModel):
    seq: str
    cliente: str
    telefono: str
    fecha: datetime.date
    enviado: datetime.date | None
    estado: str
    total_cents: int


class BudgetsExportRequest(BaseModel):
    period_label: str
    budgets: list[BudgetsExportRow] = Field(default_factory=list)


# ─── Presupuesto individual (ReportLab) ───────────────────────────────


class BudgetItemRequest(BaseModel):
    product_name: str
    qty: int
    unit_selling: Decimal
    line_selling: Decimal


class BudgetPdfRequest(BaseModel):
    seq: str
    version: int
    created_at: datetime.datetime | None = None
    customer_name: str
    customer_phone: str
    delivery_address: str | None = None
    items: list[BudgetItemRequest] = Field(default_factory=list)
    subtotal: Decimal
    total: Decimal  # total_venta (con IVA)
    iva_pct: Decimal = Decimal("21")
    business_name: str = ""
    footer_text: str = ""

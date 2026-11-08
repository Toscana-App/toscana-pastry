"""Tests de la API HTTP del binario pdfgenerator (TestClient, sin servidor).

Verifica que cada endpoint de /render/* acepta el DTO, valida el schema y
devuelve bytes de PDF (application/pdf). El pricelist (WeasyPrint) requiere
Pango en el sistema; si no esta disponible se marca como skip.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from pdfgenerator.server import app

client = TestClient(app)


def _has_pango() -> bool:
    try:
        from weasyprint import HTML  # noqa: F401

        HTML(string="<p>x</p>").render()
        return True
    except Exception:
        return False


requires_pango = pytest.mark.skipif(not _has_pango(), reason="WeasyPrint/Pango no disponible")


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["service"] == "pdfgenerator"
    assert r.json()["status"] == "ok"


def test_render_weekly():
    body = {
        "monday": "2026-11-02",
        "sunday": "2026-11-08",
        "orders": [
            {"fecha": "2026-11-02", "cliente": "Juan Pérez", "items": 3,
             "total_cents": 1234567, "paid": True, "metodo": "efectivo"},
        ],
        "total_cents": 1234567,
        "paid_cents": 1234567,
    }
    r = client.post("/render/weekly", json=body)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")


def test_render_orders_export():
    body = {
        "period_label": "2026-11-02 a 2026-11-08",
        "orders": [
            {"id": "o-1", "cliente": "Juan Pérez", "fecha": "2026-11-02",
             "items": 3, "total_cents": 1234567, "estado": "confirmado",
             "paid": True, "metodo": "efectivo"},
        ],
    }
    r = client.post("/render/orders-export", json=body)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_render_budgets_export():
    body = {
        "period_label": "todos",
        "budgets": [
            {"seq": "00042", "cliente": "María Gómez", "telefono": "+54 9 11 5555-0100",
             "fecha": "2026-11-01", "enviado": "2026-11-01", "estado": "enviado",
             "total_cents": 452000},
        ],
    }
    r = client.post("/render/budgets-export", json=body)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_render_budget():
    body = {
        "seq": "#00001",
        "version": 1,
        "created_at": "2026-11-02T10:00:00Z",
        "customer_name": "María Fernanda",
        "customer_phone": "5493571234567",
        "delivery_address": None,
        "items": [
            {"product_name": "Torta de Limón", "qty": 2,
             "unit_selling": "1550.00", "line_selling": "3100.00"},
        ],
        "subtotal": "3100.00",
        "total": "3751.00",
        "iva_pct": "21",
        "business_name": "Toscana Pastry",
        "footer_text": "",
    }
    r = client.post("/render/budget", json=body)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")


def test_render_budget_rejects_bad_schema():
    body = {"seq": "x"}  # falta version, items, totales, etc.
    r = client.post("/render/budget", json=body)
    assert r.status_code == 422


@requires_pango
def test_render_pricelist():
    body = {
        "audience_label": "Revendedores",
        "rows": [{"name": "Torta de Limón", "unit": "un", "price": "$1.000,00"}],
    }
    r = client.post("/render/pricelist", json=body)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")

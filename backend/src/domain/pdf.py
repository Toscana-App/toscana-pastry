"""PDF del presupuesto (Fase 8, P9).

Puerto `PdfRenderer`: presupuesto de dominio + branding del negocio →
bytes de PDF. La implementación (ReportLab) vive en data/pdf.

Seguridad (P9): el render solo toca el snapshot del cliente —
productos, cantidades, precios de venta, subtotal, IVA y total —
NUNCA unit_cost, total_costos, ganancia ni margen. La suite de tests
lo garantiza (el texto extraído del PDF no contiene esos términos).

Cache por hash de contenido: `budget_content_hash` se calcula sobre
exactamente lo que se renderiza. Presupuesto editado → hash nuevo →
documento regenerado (invalidación por edición, P9).
"""
import hashlib
import json
from abc import ABC, abstractmethod
from decimal import ROUND_HALF_UP
from decimal import Decimal

from domain.budgets import Budget, IVA_PCT


def format_money_peso(amount: Decimal) -> str:
    """Dinero en formato es-AR para el documento: $1.550,00
    (punto separador de miles, coma decimales)."""
    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if q < 0 else ""
    q = abs(q)
    integer, cents = f"{q:.2f}".split(".")
    groups = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    return f"{sign}${'.'.join(groups)},{cents}"


def budget_content_hash(budget: Budget, business_name: str, footer_text: str) -> str:
    """SHA-256 de exactamente lo que el PDF renderiza (sin costos ni
    margen). Mismo documento → mismo hash; editado cliente, precios o
    branding → hash nuevo (cache invalidada)."""
    totals = budget.totals
    payload = {
        "seq": budget.seq,
        "version": budget.version,
        "customer": {"name": budget.customer_name, "phone": budget.customer_phone},
        "items": [
            {
                "name": item.product_name,
                "qty": item.qty,
                "unit_selling": str(item.unit_selling),
                "line_selling": str(item.line_selling),
            }
            for item in budget.items
        ],
        "subtotal": str(totals.subtotal),
        "iva": str(totals.iva),
        "iva_pct": str(IVA_PCT),
        "total": str(totals.subtotal + totals.iva),
        "brand": {"business_name": business_name, "footer_text": footer_text},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PdfRenderer(ABC):
    """Puerto de render: solo el snapshot del cliente (P9) — productos,
    cantidades, precios de venta, subtotal, IVA y total; nunca costos,
    ganancia ni margen."""

    @abstractmethod
    def render(self, budget: Budget, business_name: str, footer_text: str) -> bytes:
        pass

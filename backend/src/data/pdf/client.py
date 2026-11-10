from __future__ import annotations

import httpx

from domain.budgets import IVA_PCT
from domain.budgets import Budget
from domain.pdf import PdfRenderer


class PdfServiceError(RuntimeError):
    pass


def budget_pdf_payload(budget: Budget, business_name: str, footer_text: str) -> dict:
    totals = budget.totals
    return {
        "seq": str(budget.seq),
        "version": budget.version,
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "customer_name": budget.customer_name,
        "customer_phone": budget.customer_phone,
        "delivery_address": budget.delivery_address,
        "items": [
            {
                "product_name": it.product_name,
                "qty": it.qty,
                "unit_selling": str(it.unit_selling),
                "line_selling": str(it.line_selling),
            }
            for it in budget.items
        ],
        "subtotal": str(totals.subtotal),
        "iva": str(totals.iva),
        "total": str(totals.total_venta),
        "iva_pct": str(IVA_PCT),
        "business_name": business_name,
        "footer_text": footer_text,
    }


class PdfClient(PdfRenderer):

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _post(self, path: str, payload: dict) -> bytes:
        try:
            resp = httpx.post(
                f"{self._base_url}{path}", json=payload, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise PdfServiceError(f"pdfgenerator no responde: {exc}") from exc
        if resp.status_code != 200:
            raise PdfServiceError(f"pdfgenerator devolvió HTTP {resp.status_code}")
        return resp.content

    def render(self, budget: Budget, business_name: str, footer_text: str) -> bytes:
        return self._post(
            "/render/budget", budget_pdf_payload(budget, business_name, footer_text)
        )

    def render_weekly(self, payload: dict) -> bytes:
        return self._post("/render/weekly", payload)

    def render_orders_export(self, payload: dict) -> bytes:
        return self._post("/render/orders-export", payload)

    def render_budgets_export(self, payload: dict) -> bytes:
        return self._post("/render/budgets-export", payload)

    def render_pricelist(
        self,
        rows: list[dict],
        audience_label: str,
        business_name: str = "",
        footer_text: str = "",
    ) -> bytes:
        return self._post(
            "/render/pricelist",
            {
                "audience_label": audience_label,
                "rows": rows,
                "business_name": business_name,
                "footer_text": footer_text,
            },
        )

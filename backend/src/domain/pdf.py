import hashlib
import json
from abc import ABC, abstractmethod
from decimal import ROUND_HALF_UP
from decimal import Decimal

from domain.budgets import Budget, IVA_PCT


def format_money_peso(amount: Decimal) -> str:
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

    @abstractmethod
    def render(self, budget: Budget, business_name: str, footer_text: str) -> bytes:
        pass

import pytest_asyncio
from sqlalchemy import text

from pg_support import make_test_engine
from data.models import Base
from main import app
from api.v1.pdf.dependencies import get_pdf_client
from data.pdf.client import budget_pdf_payload


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    engine = make_test_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await engine.dispose()


class _FakePdfClient:

    def __init__(self) -> None:
        self.last_budget_payload: dict | None = None
        self.calls: list[tuple[str, object]] = []

    def render(self, budget, business_name: str, footer_text: str) -> bytes:
        self.last_budget_payload = budget_pdf_payload(budget, business_name, footer_text)
        self.calls.append(("render", self.last_budget_payload))
        return b"%PDF-1.4\n%fake pdfgenerator\n%%EOF\n"

    def render_weekly(self, payload: dict) -> bytes:
        self.calls.append(("render_weekly", payload))
        return b"%PDF-1.4\n%fake\n%%EOF\n"

    def render_orders_export(self, payload: dict) -> bytes:
        self.calls.append(("render_orders_export", payload))
        return b"%PDF-1.4\n%fake\n%%EOF\n"

    def render_budgets_export(self, payload: dict) -> bytes:
        self.calls.append(("render_budgets_export", payload))
        return b"%PDF-1.4\n%fake\n%%EOF\n"

    def render_pricelist(
        self,
        rows: list[dict],
        audience_label: str,
        business_name: str = "",
        footer_text: str = "",
    ) -> bytes:
        self.calls.append(("render_pricelist", (rows, audience_label)))
        return b"%PDF-1.4\n%fake\n%%EOF\n"


@pytest_asyncio.fixture(autouse=True)
async def pdf_fake():
    fake = _FakePdfClient()
    app.dependency_overrides[get_pdf_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_pdf_client, None)

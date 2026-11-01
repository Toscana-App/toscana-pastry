"""Regression tests for PR #23 review fixes (no-leak, CSV injection, PDF 503,
full-list pagination, resolve_audience)."""

import csv
import sys
import types
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from data.accent import accent_fold
from data.models import Base
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import Ingredient, User, UserRole
from domain.pricing_service import AudienceForbiddenError, resolve_audience

SETTINGS = "/api/v1/tenant/settings"
DUAL = "/api/v1/pricing/preview/dual"
CSV = "/api/v1/products/pricelist/csv"
PDF = "/api/v1/products/pricelist/pdf"
PRODUCTS = "/api/v1/products"

ITEMS = [
    {"qty": "250", "unit": "g", "price_per_purchase_unit": 280000, "purchase_unit": "kg"},
]
LEAKY = {"base", "materials", "labor", "gas", "margin_pct", "waste", "materials_con_merma"}


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fn(dbapi_connection, connection_record):
        dbapi_connection.create_function("accent_fold", 1, accent_fold, deterministic=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:

        async def db():
            yield session

        async def users():
            yield SQLUserRepository(session)

        async def sets():
            yield SQLSettingsRepository(session)

        async def ings():
            yield SQLIngredientRepository(session)

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_user_repository] = users
        app.dependency_overrides[get_settings_repository] = sets
        app.dependency_overrides[get_ingredient_repository] = ings
        for email, role in [
            ("admin@example.com", UserRole.ADMIN),
            ("negocio@example.com", UserRole.NEGOCIO),
            ("cliente@example.com", UserRole.CUSTOMER),
        ]:
            await SQLUserRepository(session).save(User(email=email, role=role))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.session = session  # type: ignore[attr-defined]
            try:
                yield ac
            finally:
                app.dependency_overrides = {}


async def _h(ac, email):
    r = await ac.post("/api/v1/auth/login", json={"email": email})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _add(ac, name, price="100"):
    await SQLIngredientRepository(ac.session).create(
        Ingredient(name=name, unit="kg", price_per_unit=Decimal(price), stock_qty=Decimal("5"))
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "email,aud",
    [("negocio@example.com", "revendedores"), ("cliente@example.com", "consumidor_final")],
)
async def test_preview_dual_non_admin_only_audience_and_price(client, email, aud):
    r = await client.post(
        DUAL, json={"line_items": ITEMS, "prep_minutes": 30}, headers=await _h(client, email)
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"audience", "price"}
    assert body["audience"] == aud
    assert not (LEAKY | {"rounded", "final"}) & set(body)


@pytest.mark.asyncio
async def test_preview_dual_admin_keeps_full_breakdown(client):
    r = await client.post(
        DUAL,
        json={"line_items": ITEMS, "prep_minutes": 30, "audience": "consumidor_final"},
        headers=await _h(client, "admin@example.com"),
    )
    assert r.status_code == 200
    assert LEAKY <= set(r.json())


@pytest.mark.asyncio
@pytest.mark.parametrize("email", ["negocio@example.com", "cliente@example.com"])
async def test_get_settings_hides_consumer_markup_for_non_admin(client, email):
    r = await client.get(SETTINGS, headers=await _h(client, email))
    assert r.status_code == 200
    assert "consumer_markup_pct" not in r.json()
    assert "hourly_rate" in r.json()


@pytest.mark.asyncio
async def test_get_settings_admin_sees_consumer_markup(client):
    r = await client.get(SETTINGS, headers=await _h(client, "admin@example.com"))
    assert r.status_code == 200
    assert Decimal(r.json()["consumer_markup_pct"]) == Decimal("40")


@pytest.mark.asyncio
async def test_csv_neutralizes_formula_injection(client):
    await _add(client, '=HYPERLINK("http://evil","x")')
    await _add(client, "+cmd")
    await _add(client, "-1+1")
    await _add(client, "@SUM(A1)")
    await _add(client, "Harina")
    r = await client.get(
        CSV, params={"audience": "revendedores"}, headers=await _h(client, "admin@example.com")
    )
    rows = list(csv.reader(r.content.decode().splitlines()))[1:]
    names = {row[0] for row in rows}
    assert "'=HYPERLINK(\"http://evil\",\"x\")" in names
    assert {"'+cmd", "'-1+1", "'@SUM(A1)", "Harina"} <= names
    assert not any(n.startswith(("=", "+", "-", "@")) for n in names)


@pytest.mark.asyncio
async def test_lists_and_csv_are_not_truncated_by_page_size(client, monkeypatch):
    import api.v1.products.router as pr

    monkeypatch.setattr(pr, "_LIST_PAGE_SIZE", 2)
    for i in range(5):
        await _add(client, f"Item {i}")
    h = await _h(client, "admin@example.com")
    r = await client.get(PRODUCTS, params={"audience": "revendedores"}, headers=h)
    assert r.json()["total"] == 5 and len(r.json()["products"]) == 5
    c = await client.get(CSV, params={"audience": "revendedores"}, headers=h)
    assert len(c.content.decode().strip().splitlines()) == 6


@pytest.mark.asyncio
async def test_pdf_render_failure_is_generic_503(client, monkeypatch):
    await _add(client, "Harina")

    class Boom:
        def __init__(self, *a, **k):
            pass

        def render(self):
            raise OSError("cannot load library /secret/path/libpango.so")

    fake = types.ModuleType("weasyprint")
    fake.HTML = Boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "weasyprint", fake)
    r = await client.get(
        PDF, params={"audience": "revendedores"}, headers=await _h(client, "admin@example.com")
    )
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "secret" not in r.text and "libpango" not in r.text


def test_resolve_audience_public_with_enums():
    assert resolve_audience(UserRole.NEGOCIO, None) == "revendedores"
    assert resolve_audience(UserRole.CUSTOMER, None) == "consumidor_final"
    assert resolve_audience(UserRole.ADMIN, "consumidor_final") == "consumidor_final"
    assert resolve_audience(UserRole.ADMIN, None) == "revendedores"
    with pytest.raises(AudienceForbiddenError):
        resolve_audience(UserRole.CUSTOMER, "revendedores")
    with pytest.raises(AudienceForbiddenError):
        resolve_audience("unknown-role", None)

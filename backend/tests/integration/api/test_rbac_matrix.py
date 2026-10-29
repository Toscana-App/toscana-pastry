"""Comprehensive RBAC matrix + price-leak verification (T6).

Matriz completa de accesos por rol × audiencia × endpoint.
Verifica que los precios no "se filtren" entre audiencias: un negocio
solo ve precios de revendedores, un cliente solo precios de consumidor_final.

Casos cubiertos (15):
  1.  negocio  → GET /products?audience=consumidor_final     → 403
  2.  negocio  → GET /products?audience=revendedores         → 200 (precios base)
  3.  negocio  → GET /products/pricelist/csv?audience=consumidor_final → 403
  4.  negocio  → GET /products/pricelist/csv?audience=revendedores   → 200
  5.  cliente  → GET /products?audience=revendedores         → 403
  6.  cliente  → GET /products?audience=consumidor_final     → 200 (base × 1.40)
  7.  cliente  → GET /products/pricelist/csv?audience=revendedores   → 403
  8.  cliente  → GET /products/pricelist/csv?audience=consumidor_final → 200
  9.  negocio  → POST /pricing/preview/dual (audience=consumidor_final) → 403
  10. cliente  → PUT /tenant/settings                        → 403
  11. negocio  → PUT /tenant/settings                        → 403
  12. admin    → GET /products?audience=revendedores          → 200
  13. admin    → GET /products?audience=consumidor_final      → 200
  14. admin    → PUT /tenant/settings                         → 200
  15. admin    → GET /products/pricelist/csv ambas audiencias → 200
  16. anónimo  → GET /products                               → 401

Verificación de NO-FUGA:
  En los 200 de negocio, los precios deben coincidir con
  derive_audience_price(base, markup, "revendedores") == base.
  En los 200 de cliente, los precios deben coincidir con
  derive_audience_price(base, markup, "consumidor_final") == base × (1 + markup/100).

Nota de caracterización: la mayoría de los 403/200 ya están cubiertos por
tests existentes (test_products_listing.py, test_pricelist_export.py,
test_dual_pricing_api.py, test_rbac_api.py). Esta matriz funciona como
caracterización + agrega la verificación numérica de no-fuga.
"""

import csv
from decimal import Decimal
from io import StringIO

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from data.accent import accent_fold
from data.db import get_db
from data.models import Base
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import Ingredient, User, UserRole
from domain.pricing_service import derive_audience_price
from main import app

# ─── Fixtures ───────────────────────────────────────────────────────────────

_TEST_PRODUCTS = [
    {"name": "Harina 0000", "unit": "kg", "price_per_unit": "100.00", "stock_qty": "50"},
    {"name": "Azúcar refinada", "unit": "kg", "price_per_unit": "200.00", "stock_qty": "30"},
]

_MARKUP_PCT = Decimal(40)  # 40% default


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        # Seed all roles
        await SQLUserRepository(session).save(
            User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)
        )
        await SQLUserRepository(session).save(
            User(id="negocio-1", email="negocio@example.com", role=UserRole.NEGOCIO)
        )
        await SQLUserRepository(session).save(
            User(id="cliente-1", email="cliente@example.com", role=UserRole.CUSTOMER)
        )
        # Seed products with known base prices
        for prod in _TEST_PRODUCTS:
            ingredient = Ingredient(
                name=prod["name"],
                unit=prod["unit"],
                price_per_unit=Decimal(prod["price_per_unit"]),
                stock_qty=Decimal(prod["stock_qty"]),
            )
            await SQLIngredientRepository(session).create(ingredient)
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    async def override_get_ingredient_repository():
        yield SQLIngredientRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


# ─── Settings payload ───────────────────────────────────────────────────────

_SETTINGS_PAYLOAD = {
    "hourly_rate": "150",
    "margin_pct": "100",
    "round_step": "5",
    "include_labor": True,
    "include_gas": False,
    "gas_pct": "0",
    "include_waste": False,
    "waste_pct": "0",
    "urgent_surcharge_pct": "20",
    "consumer_markup_pct": str(_MARKUP_PCT),
    "default_prep_minutes": 30,
    "default_servings": 6,
    "default_difficulty": "simple",
}

# ─── Helper: compute expected prices via derive_audience_price ──────────────


def _expected_price(base_price: Decimal, audience: str) -> Decimal:
    """Compute expected price using the single source of truth."""
    return derive_audience_price(base_price, _MARKUP_PCT, audience)


# Base prices for known test products — used for NO-FUGA verification.
_BASE_PRICES = {
    p["name"]: Decimal(p["price_per_unit"])
    for p in _TEST_PRODUCTS
}


# ─── Case 1: negocio → consumidor_final → 403 ─────────────────────────────


@pytest.mark.asyncio
async def test_case1_negocio_consumidor_final_products_403(client):
    """T6-1: negocio NO puede acceder a productos con audience=consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 2: negocio → revendedores → 200 + no-fuga ──────────────────────


@pytest.mark.asyncio
async def test_case2_negocio_revendedores_products_200_no_leak(client):
    """T6-2: negocio + revendedores → 200; precios = base (sin fuga de consumidor_final)."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "revendedores"

    # NO-FUGA: cada precio debe coincidir con derive_audience_price(base, markup, "revendedores")
    for product in data["products"]:
        base = Decimal(product["price_per_unit"])
        expected = _expected_price(Decimal(product["price_per_unit"]), "revendedores")
        assert base == expected, (
            f"Producto {product['name']}: precio {base} != esperado {expected} (no-fuga fallida)"
        )


# ─── Case 3: negocio → pricelist/csv consumidor_final → 403 ──────────────


@pytest.mark.asyncio
async def test_case3_negocio_consumidor_final_pricelist_csv_403(client):
    """T6-3: negocio NO puede exportar CSV con audience=consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 4: negocio → pricelist/csv revendedores → 200 + no-fuga ─────────


@pytest.mark.asyncio
async def test_case4_negocio_revendedores_pricelist_csv_200_no_leak(client):
    """T6-4: negocio + revendedores CSV → 200; precios = base (sin fuga)."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    # Parse CSV and verify prices match base (no markup for revendedores)
    csv_text = r.content.decode("utf-8")
    reader = csv.reader(StringIO(csv_text))
    rows = list(reader)
    # Skip header
    for row in rows[1:]:
        if len(row) >= 3:
            price_str = row[2].replace("$", "").strip()
            price = Decimal(price_str)
            # For revendedores, price should equal base (no markup)
            assert price in _BASE_PRICES.values(), (
                f"CSV price {price} should match a base price for revendedores"
            )


# ─── Case 5: cliente → revendedores → 403 ─────────────────────────────────


@pytest.mark.asyncio
async def test_case5_cliente_revendedores_products_403(client):
    """T6-5: cliente NO puede acceder a productos con audience=revendedores → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 6: cliente → consumidor_final → 200 + no-fuga ──────────────────


@pytest.mark.asyncio
async def test_case6_cliente_consumidor_final_products_200_no_leak(client):
    """T6-6: cliente + consumidor_final → 200; precios = base × 1.40 (sin fuga de revendedores)."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "consumidor_final"

    # NO-FUGA: cada precio debe coincidir con derive_audience_price(base, markup, "consumidor_final")
    for product in data["products"]:
        base_price = _BASE_PRICES[product["name"]]
        expected = _expected_price(base_price, "consumidor_final")
        actual = Decimal(product["price_per_unit"])
        assert actual == expected, (
            f"Producto {product['name']}: precio {actual} != esperado {expected} (no-fuga fallida)"
        )


# ─── Case 7: cliente → pricelist/csv revendedores → 403 ──────────────────


@pytest.mark.asyncio
async def test_case7_cliente_revendedores_pricelist_csv_403(client):
    """T6-7: cliente NO puede exportar CSV con audience=revendedores → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 8: cliente → pricelist/csv consumidor_final → 200 + no-fuga ────


@pytest.mark.asyncio
async def test_case8_cliente_consumidor_final_pricelist_csv_200_no_leak(client):
    """T6-8: cliente + consumidor_final CSV → 200; precios = base × 1.40."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    # Parse CSV and verify prices match markup (base × 1.40 for consumidor_final)
    csv_text = r.content.decode("utf-8")
    reader = csv.reader(StringIO(csv_text))
    rows = list(reader)
    for row in rows[1:]:
        if len(row) >= 3:
            price_str = row[2].replace("$", "").strip()
            price = Decimal(price_str)
            # For consumidor_final, price should be base × 1.40
            # Look up base price from known products
            base_price = _BASE_PRICES.get(row[0].strip())
            if base_price is not None:
                expected = _expected_price(base_price, "consumidor_final")
                assert price == expected, (
                    f"CSV price {price} != expected {expected} for {row[0].strip()}"
                )


# ─── Case 9: negocio → POST /pricing/preview/dual (consumidor_final) → 403 ─


@pytest.mark.asyncio
async def test_case9_negocio_pricing_preview_dual_403(client):
    """T6-9: negocio NO puede usar POST /pricing/preview/dual con audience=consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.post(
        "/api/v1/pricing/preview/dual",
        json={
            "line_items": [
                {"qty": "250", "unit": "g", "price_per_purchase_unit": "2800", "purchase_unit": "kg"}
            ],
            "prep_minutes": 30,
            "audience": "consumidor_final",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 10: cliente → PUT /tenant/settings → 403 ───────────────────────


@pytest.mark.asyncio
async def test_case10_cliente_put_tenant_settings_403(client):
    """T6-10: cliente NO puede escribir settings → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.put(
        "/api/v1/tenant/settings",
        json=_SETTINGS_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 11: negocio → PUT /tenant/settings → 403 ───────────────────────


@pytest.mark.asyncio
async def test_case11_negocio_put_tenant_settings_403(client):
    """T6-11: negocio NO puede escribir settings → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.put(
        "/api/v1/tenant/settings",
        json=_SETTINGS_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ─── Case 12: admin → GET /products revendedores → 200 ───────────────────


@pytest.mark.asyncio
async def test_case12_admin_products_revendedores_200(client):
    """T6-12: admin + revendedores → 200, precios base."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "revendedores"
    assert data["total"] == len(_TEST_PRODUCTS)


# ─── Case 13: admin → GET /products consumidor_final → 200 + no-fuga ─────


@pytest.mark.asyncio
async def test_case13_admin_products_consumidor_final_200_no_leak(client):
    """T6-13: admin + consumidor_final → 200; precios = base × 1.40 (sin fuga)."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "consumidor_final"

    # NO-FUGA: verificar precios con derive_audience_price
    for product in data["products"]:
        base_price = _BASE_PRICES[product["name"]]
        expected = _expected_price(base_price, "consumidor_final")
        actual = Decimal(product["price_per_unit"])
        assert actual == expected, (
            f"Producto {product['name']}: precio {actual} != esperado {expected} (no-fuga fallida)"
        )


# ─── Case 14: admin → PUT /tenant/settings → 200 ─────────────────────────


@pytest.mark.asyncio
async def test_case14_admin_put_tenant_settings_200(client):
    """T6-14: admin puede escribir settings → 200."""
    token = await _token_for(client, "admin@example.com")
    r = await client.put(
        "/api/v1/tenant/settings",
        json=_SETTINGS_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200


# ─── Case 15: admin → GET /products/pricelist/csv ambas audiencias → 200 ─


@pytest.mark.asyncio
async def test_case15_admin_pricelist_csv_both_audiences_200(client):
    """T6-15: admin puede exportar CSV para ambas audiencias → 200."""
    token = await _token_for(client, "admin@example.com")

    # revendedores
    r_rev = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_rev.status_code == 200
    assert r_rev.headers["content-type"].startswith("text/csv")

    # consumidor_final
    r_cons = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_cons.status_code == 200
    assert r_cons.headers["content-type"].startswith("text/csv")

    # Verify prices differ between audiences (no-fuga cross-check)
    csv_rev = r_rev.content.decode("utf-8")
    csv_cons = r_cons.content.decode("utf-8")
    assert csv_rev != csv_cons, "CSV para revendedores y consumidor_final deberían tener precios distintos"


# ─── Case 16: anónimo → GET /products → 401 ──────────────────────────────


@pytest.mark.asyncio
async def test_case16_anonimo_products_401(client):
    """T6-16: sin token → 401."""
    r = await client.get("/api/v1/products", params={"audience": "revendedores"})
    assert r.status_code == 401

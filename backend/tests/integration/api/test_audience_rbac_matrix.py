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
import uuid
from decimal import Decimal
from io import StringIO

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.settings.dependencies import get_settings_repository
from data.db import get_db
from data.models import BusinessSettingsORM, ProductORM, RecipeItemORM
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
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
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    async def override_get_ingredient_repository():
        yield SQLIngredientRepository(db_session)

    async def override_get_product_repository():
        yield SQLProductRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository

    user_repo = SQLUserRepository(db_session)
    for _email, _role in (
        ("admin@example.com", UserRole.ADMIN),
        ("negocio@example.com", UserRole.NEGOCIO),
        ("cliente@example.com", UserRole.CUSTOMER),
    ):
        await user_repo.save(User(email=_email, role=_role))

    db_session.add(
        BusinessSettingsORM(
            hourly_rate="1",
            margin_pct="0",
            round_step="0.01",
            gas_pct="0",
            waste_pct="0",
            consumer_markup_pct=str(_MARKUP_PCT),
            include_labor=False,
            include_gas=False,
            include_waste=False,
            default_prep_minutes=0,
            default_servings=6,
            default_difficulty="simple",
            business_name="",
            footer_text="",
        )
    )
    ingredient_repo = SQLIngredientRepository(db_session)
    for _p in _TEST_PRODUCTS:
        ingredient = await ingredient_repo.create(
            Ingredient(
                name=_p["name"],
                unit=_p["unit"],
                price_per_unit=Decimal(_p["price_per_unit"]),
                stock_qty=Decimal(_p["stock_qty"]),
            )
        )
        product_id = str(uuid.uuid4())
        product = ProductORM(
            id=product_id,
            name=_p["name"],
            category="General",
            description="",
            prep_time_min=0,
            servings=6,
            difficulty="simple",
            available=True,
        )
        product.recipe_items = [
            RecipeItemORM(
                id=str(uuid.uuid4()),
                product_id=product_id,
                ingredient_id=ingredient.id,
                qty="1",
                unit=_p["unit"],
                position=0,
            )
        ]
        db_session.add(product)
    await db_session.commit()

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
    "hourly_rate": 15000,
    "margin_pct": "100",
    "round_step": 500,
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


def _parse_pricelist(csv_text: str) -> dict[str, Decimal]:
    """Parse a pricelist CSV by header name; assert shape and product coverage."""
    reader = csv.DictReader(StringIO(csv_text))
    assert reader.fieldnames == ["name", "category", "price"]
    rows = list(reader)
    assert len(rows) == len(_TEST_PRODUCTS)
    prices: dict[str, Decimal] = {}
    for row in rows:
        assert row["name"] in _BASE_PRICES, f"Unknown product in CSV: {row['name']}"
        prices[row["name"]] = Decimal(row["price"].replace("$", "").strip())
    assert set(prices) == set(_BASE_PRICES)
    return prices


_PREVIEW_BODY = {
    "line_items": [
        {"qty": "250", "unit": "g", "price_per_purchase_unit": 280000, "purchase_unit": "kg"}
    ],
    "prep_minutes": 30,
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
    assert len(data["products"]) == len(_TEST_PRODUCTS)
    for product in data["products"]:
        expected = _expected_price(_BASE_PRICES[product["name"]], "revendedores")
        actual = Decimal(product["price"])
        assert actual == expected, (
            f"Producto {product['name']}: precio {actual} != esperado {expected} (no-fuga fallida)"
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

    # Parse CSV by header; revendedores price must equal the known base price
    prices = _parse_pricelist(r.content.decode("utf-8"))
    for name, price in prices.items():
        expected = _expected_price(_BASE_PRICES[name], "revendedores")
        assert price == expected, f"CSV price {price} != base {expected} for {name}"


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
    assert len(data["products"]) == len(_TEST_PRODUCTS)
    for product in data["products"]:
        base_price = _BASE_PRICES[product["name"]]
        expected = _expected_price(base_price, "consumidor_final")
        actual = Decimal(product["price"])
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

    # Parse CSV by header; consumidor_final price must equal base x 1.40
    prices = _parse_pricelist(r.content.decode("utf-8"))
    for name, price in prices.items():
        expected = _expected_price(_BASE_PRICES[name], "consumidor_final")
        assert price == expected, f"CSV price {price} != expected {expected} for {name}"


# ─── Case 9: negocio → POST /pricing/preview/dual (consumidor_final) → 403 ─


@pytest.mark.asyncio
async def test_case9_negocio_pricing_preview_dual_403(client):
    """T6-9: negocio NO puede usar POST /pricing/preview/dual con audience=consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.post(
        "/api/v1/pricing/preview/dual",
        json={
            "line_items": [
                {"qty": "250", "unit": "g", "price_per_purchase_unit": 280000, "purchase_unit": "kg"}
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
    assert len(data["products"]) == len(_TEST_PRODUCTS)
    for product in data["products"]:
        base_price = _BASE_PRICES[product["name"]]
        expected = _expected_price(base_price, "consumidor_final")
        actual = Decimal(product["price"])
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
    r = await client.put(
        "/api/v1/tenant/settings",
        json={
            "hourly_rate": 1,
            "margin_pct": "0",
            "round_step": 1,
            "include_labor": False,
            "include_gas": False,
            "gas_pct": "0",
            "include_waste": False,
            "waste_pct": "0",
            "urgent_surcharge_pct": "20",
            "consumer_markup_pct": str(_MARKUP_PCT),
            "default_prep_minutes": 0,
            "default_servings": 6,
            "default_difficulty": "simple",
        },
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

    # Per-product prices must match each audience's expected price
    rev = _parse_pricelist(r_rev.content.decode("utf-8"))
    cons = _parse_pricelist(r_cons.content.decode("utf-8"))
    for name, base in _BASE_PRICES.items():
        assert rev[name] == _expected_price(base, "revendedores")
        assert cons[name] == _expected_price(base, "consumidor_final")


# ─── Case 16: anónimo → GET /products → 401 ──────────────────────────────


@pytest.mark.asyncio
async def test_case16_anonimo_products_401(client):
    """T6-16: sin token → 401."""
    r = await client.get("/api/v1/products", params={"audience": "revendedores"})
    assert r.status_code == 401


# ─── Extra cases: preview/dual for all roles + anonymous 401 ─────────────


@pytest.mark.asyncio
async def test_case17_cliente_preview_dual_revendedores_403(client):
    """cliente + audience=revendedores en preview/dual → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.post(
        "/api/v1/pricing/preview/dual",
        json={**_PREVIEW_BODY, "audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_case18_admin_preview_dual_200_both_audiences(client):
    """admin → preview/dual 200 para ambas audiencias; consumidor = derive(revendedores)."""
    token = await _token_for(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r_rev = await client.post(
        "/api/v1/pricing/preview/dual",
        json={**_PREVIEW_BODY, "audience": "revendedores"},
        headers=headers,
    )
    r_cons = await client.post(
        "/api/v1/pricing/preview/dual",
        json={**_PREVIEW_BODY, "audience": "consumidor_final"},
        headers=headers,
    )
    assert r_rev.status_code == 200
    assert r_cons.status_code == 200
    assert r_rev.json()["audience"] == "revendedores"
    assert r_cons.json()["audience"] == "consumidor_final"
    rev_price = Decimal(r_rev.json()["rounded"])
    assert Decimal(r_cons.json()["rounded"]) == _expected_price(rev_price, "consumidor_final")


@pytest.mark.asyncio
async def test_case19_negocio_preview_dual_amounts_no_leak(client):
    """negocio → preview/dual 200 con importes de revendedores (iguales a los del admin)."""
    admin_token = await _token_for(client, "admin@example.com")
    admin_r = await client.post(
        "/api/v1/pricing/preview/dual",
        json={**_PREVIEW_BODY, "audience": "revendedores"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    admin_cons = await client.post(
        "/api/v1/pricing/preview/dual",
        json={**_PREVIEW_BODY, "audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_r.status_code == 200
    assert admin_cons.status_code == 200

    token = await _token_for(client, "negocio@example.com")
    r = await client.post(
        "/api/v1/pricing/preview/dual",
        json=_PREVIEW_BODY,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["audience"] == "revendedores"
    # PR #23 review fix: non-admin roles only get {audience, price} (no cost
    # breakdown, no base price).
    assert set(body) == {"audience", "price"}
    assert Decimal(body["price"]) == Decimal(admin_r.json()["rounded"])
    assert Decimal(body["price"]) != Decimal(admin_cons.json()["rounded"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/products/pricelist/csv?audience=revendedores", None),
        ("POST", "/api/v1/pricing/preview/dual", _PREVIEW_BODY),
        ("PUT", "/api/v1/tenant/settings", _SETTINGS_PAYLOAD),
    ],
)
async def test_case20_anonimo_protected_endpoints_401(client, method, path, payload):
    """Sin token → 401 en pricelist/csv, pricing/preview/dual y PUT /tenant/settings."""
    r = await client.request(method, path, json=payload)
    assert r.status_code == 401

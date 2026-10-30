"""Tests para exportación de lista de precios CSV/PDF por audiencia (S3 — T4).

Reglas cubiertas:
  1) admin → ambas audiencias (CSV y PDF) OK
  2) negocio → revendedores OK; consumidor_final → 403
  3) cliente → consumidor_final OK; revendedores → 403
  4) audience inválida → 422
  5) CSV: filas de productos con precio de la audiencia
  6) PDF: content-type application/pdf + bytes %PDF (skip if weasyprint libs missing)
"""

import csv
from decimal import Decimal

from pg_support import make_test_engine
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from main import app
from data.models import Base
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole, Ingredient

# Check weasyprint rendering capability at import time.
# WeasyPrint on Windows requires Pango/GObject system libraries.
# If unavailable, PDF tests skip with an explicit reason.
_WEASYPRINT_RENDER_OK = False
try:
    from weasyprint import HTML

    # Try a minimal render to confirm the full stack works
    HTML(string="<html><body>test</body></html>").render()
    _WEASYPRINT_RENDER_OK = True
except OSError:
    _WEASYPRINT_RENDER_OK = False

PRICELIST_CSV = "/api/v1/products/pricelist/csv"
PRICELIST_PDF = "/api/v1/products/pricelist/pdf"

# Ingredientes que sirven como productos en la lista de precios
_TEST_PRODUCTS = [
    {"name": "Harina 0000", "unit": "kg", "price_per_unit": "2800", "stock_qty": "50"},
    {"name": "Azúcar refinada", "unit": "kg", "price_per_unit": "3500", "stock_qty": "30"},
    {"name": "Manteca sin sal", "unit": "kg", "price_per_unit": "8200", "stock_qty": "10"},
]


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
    app.dependency_overrides[get_settings_repository] = get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = get_ingredient_repository

    # Seed users and products
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    await SQLUserRepository(db_session).save(
        User(email="cliente@example.com", role=UserRole.CUSTOMER)
    )
    for prod in _TEST_PRODUCTS:
        ingredient = Ingredient(
            name=prod["name"],
            unit=prod["unit"],
            price_per_unit=Decimal(prod["price_per_unit"]),
            stock_qty=Decimal(prod["stock_qty"]),
        )
        await SQLIngredientRepository(db_session).create(ingredient)

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


# ─── Tests 1-4: Matriz de acceso ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_csv_revendedores(client):
    """T4-1: admin puede exportar CSV para revendedores → 200."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
async def test_admin_csv_consumidor_final(client):
    """T4-1: admin puede exportar CSV para consumidor_final → 200."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _WEASYPRINT_RENDER_OK,
    reason="WeasyPrint cannot render on this system (missing Pango/GObject libraries)",
)
async def test_admin_pdf_revendedores(client):
    """T4-1: admin puede exportar PDF para revendedores → 200."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _WEASYPRINT_RENDER_OK,
    reason="WeasyPrint cannot render on this system (missing Pango/GObject libraries)",
)
async def test_admin_pdf_consumidor_final(client):
    """T4-1: admin puede exportar PDF para consumidor_final → 200."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_negocio_csv_revendedores(client):
    """T4-2: negocio puede exportar CSV para revendedores → 200."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _WEASYPRINT_RENDER_OK,
    reason="WeasyPrint cannot render on this system (missing Pango/GObject libraries)",
)
async def test_negocio_pdf_revendedores(client):
    """T4-2: negocio puede exportar PDF para revendedores → 200."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_negocio_csv_consumidor_final_403(client):
    """T4-2: negocio NO puede exportar CSV para consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "consumidor_final" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_negocio_pdf_consumidor_final_403(client):
    """T4-2: negocio NO puede exportar PDF para consumidor_final → 403."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "consumidor_final" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cliente_csv_consumidor_final(client):
    """T4-3: cliente puede exportar CSV para consumidor_final → 200."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _WEASYPRINT_RENDER_OK,
    reason="WeasyPrint cannot render on this system (missing Pango/GObject libraries)",
)
async def test_cliente_pdf_consumidor_final(client):
    """T4-3: cliente puede exportar PDF para consumidor_final → 200."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_cliente_csv_revendedores_403(client):
    """T4-3: cliente NO puede exportar CSV para revendedores → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "revendedores" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cliente_pdf_revendedores_403(client):
    """T4-3: cliente NO puede exportar PDF para revendedores → 403."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "revendedores" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_audience_csv_422(client):
    """T4-4: audience inválida → 422."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_CSV, params={"audience": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_audience_pdf_422(client):
    """T4-4: audience inválida → 422."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        PRICELIST_PDF, params={"audience": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_csv_401(client):
    """T4: sin token → 401."""
    r = await client.get(PRICELIST_CSV, params={"audience": "revendedores"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_pdf_401(client):
    """T4: sin token → 401."""
    r = await client.get(PRICELIST_PDF, params={"audience": "revendedores"})
    assert r.status_code == 401


# ─── Test 5: Contenido CSV ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_csv_contains_product_rows_with_audience_price():
    """T4-5: el CSV tiene filas de productos con el precio de la audiencia.

    Para revendedores: precio = price_per_unit (sin markup).
    Para consumidor_final: precio = price_per_unit × 1.40 (markup default 40%).
    """
    engine = make_test_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        # Seed admin and products
        await SQLUserRepository(session).save(
            User(email="admin@example.com", role=UserRole.ADMIN)
        )
        for prod in _TEST_PRODUCTS:
            ingredient = Ingredient(
                name=prod["name"],
                unit=prod["unit"],
                price_per_unit=Decimal(prod["price_per_unit"]),
                stock_qty=Decimal(prod["stock_qty"]),
            )
            await SQLIngredientRepository(session).create(ingredient)

        async def override_get_db():
            yield session

        async def override_get_user_repository():
            yield SQLUserRepository(session)

        async def override_get_settings_repository():
            yield SQLSettingsRepository(session)

        async def override_get_ingredient_repository():
            yield SQLIngredientRepository(session)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_user_repository] = override_get_user_repository
        app.dependency_overrides[get_settings_repository] = override_get_settings_repository
        app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                token = await _token_for(ac, "admin@example.com")

                # --- revendedores: precio = price_per_unit ---
                r = await ac.get(
                    PRICELIST_CSV, params={"audience": "revendedores"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                csv_text = r.content.decode("utf-8")
                lines = csv_text.strip().splitlines()
                reader = csv.reader(lines)
                rows = list(reader)
                header = rows[0]
                assert "name" in header or "producto" in header[0].lower()
                assert "price" in header or "precio" in header[0].lower()
                assert len(rows) >= 4  # header + 3 products

                # Verificar que los precios coinciden con price_per_unit
                product_prices = {p["name"]: Decimal(p["price_per_unit"]) for p in _TEST_PRODUCTS}
                for row in rows[1:]:
                    name = row[0].strip()
                    if name in product_prices:
                        price = Decimal(row[2].replace("$", "").replace(",", "").strip())
                        assert price == product_prices[name], (
                            f"revendedores: {name} precio esperado {product_prices[name]}, obtenido {price}"
                        )

                # --- consumidor_final: precio = price_per_unit × 1.40 ---
                r = await ac.get(
                    PRICELIST_CSV, params={"audience": "consumidor_final"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                csv_text = r.content.decode("utf-8")
                lines = csv_text.strip().splitlines()
                reader = csv.reader(lines)
                rows = list(reader)
                assert len(rows) >= 4  # header + 3 products

                # Verificar que los precios tienen markup 40%
                for row in rows[1:]:
                    name = row[0].strip()
                    if name in product_prices:
                        price = Decimal(row[2].replace("$", "").replace(",", "").strip())
                        expected = (product_prices[name] * Decimal("1.40")).quantize(
                            Decimal("0.01"), rounding="ROUND_HALF_UP"
                        )
                        assert price == expected, (
                            f"consumidor_final: {name} precio esperado {expected}, obtenido {price}"
                        )
        finally:
            app.dependency_overrides.clear()


# ─── Test 6: PDF válido ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _WEASYPRINT_RENDER_OK,
    reason="WeasyPrint cannot render on this system (missing Pango/GObject libraries)",
)
async def test_pdf_content_type_and_bytes():
    """T4-6: el PDF devuelve content-type application/pdf y bytes que empiezan con %PDF.

    Nota: WeasyPrint en Windows requiere Pango. Si no está disponible,
    este test se salta con razón explícita.
    """
    engine = make_test_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await SQLUserRepository(session).save(
            User(email="admin@example.com", role=UserRole.ADMIN)
        )
        for prod in _TEST_PRODUCTS:
            ingredient = Ingredient(
                name=prod["name"],
                unit=prod["unit"],
                price_per_unit=Decimal(prod["price_per_unit"]),
                stock_qty=Decimal(prod["stock_qty"]),
            )
            await SQLIngredientRepository(session).create(ingredient)

        async def override_get_db():
            yield session

        async def override_get_user_repository():
            yield SQLUserRepository(session)

        async def override_get_settings_repository():
            yield SQLSettingsRepository(session)

        async def override_get_ingredient_repository():
            yield SQLIngredientRepository(session)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_user_repository] = override_get_user_repository
        app.dependency_overrides[get_settings_repository] = override_get_settings_repository
        app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                token = await _token_for(ac, "admin@example.com")

                r = await ac.get(
                    PRICELIST_PDF, params={"audience": "revendedores"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                assert r.headers["content-type"].startswith("application/pdf"), (
                    f"content-type esperado application/pdf, obtenido {r.headers.get('content-type')}"
                )
                assert r.content[:5] == b"%PDF-", (
                    f"PDF debe empezar con %PDF-, obtenido {r.content[:10]}"
                )
        finally:
            app.dependency_overrides.clear()


# ─── Test: CSV escaping (commas and quotes in product names) ──────────────


@pytest.mark.asyncio
async def test_csv_escapes_commas_and_quotes_in_product_names():
    """T4-fix1: product names containing commas or double-quotes must
    round-trip correctly through the CSV output.

    Regression: _build_csv was using manual comma-join which corrupts
    values containing commas or quotes.
    """
    engine = make_test_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await SQLUserRepository(session).save(
            User(email="admin@example.com", role=UserRole.ADMIN)
        )
        # Products with tricky names
        tricky = [
            Ingredient(
                name='Chocolate "premium"',
                unit='kg',
                price_per_unit=Decimal("12000"),
                stock_qty=Decimal("5"),
            ),
            Ingredient(
                name="Harina, tipo 000",
                unit="kg",
                price_per_unit=Decimal("2800"),
                stock_qty=Decimal("50"),
            ),
            Ingredient(
                name='Miel "orgánica", 1kg',
                unit="unidad",
                price_per_unit=Decimal("4500"),
                stock_qty=Decimal("20"),
            ),
        ]
        for ing in tricky:
            await SQLIngredientRepository(session).create(ing)

        async def override_get_db():
            yield session

        async def override_get_user_repository():
            yield SQLUserRepository(session)

        async def override_get_settings_repository():
            yield SQLSettingsRepository(session)

        async def override_get_ingredient_repository():
            yield SQLIngredientRepository(session)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_user_repository] = override_get_user_repository
        app.dependency_overrides[get_settings_repository] = override_get_settings_repository
        app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                token = await _token_for(ac, "admin@example.com")

                r = await ac.get(
                    PRICELIST_CSV,
                    params={"audience": "revendedores"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200
                csv_text = r.content.decode("utf-8")
                lines = csv_text.strip().splitlines()
                reader = csv.reader(lines)
                rows = list(reader)

                # Parse back with csv module — should not raise
                # and must preserve the original names
                product_names = {row[0].strip() for row in rows[1:]}
                expected_names = {
                    'Chocolate "premium"',
                    "Harina, tipo 000",
                    'Miel "orgánica", 1kg',
                }
                assert product_names == expected_names, (
                    f"CSV names mismatch. Got: {product_names}, expected: {expected_names}"
                )
        finally:
            app.dependency_overrides.clear()


# ─── Test: HTML escaping in PDF template ──────────────────────────────────


@pytest.mark.asyncio
async def test_pdf_html_escapes_product_names():
    """T4-fix2: _build_pdf_html must escape product names/units to prevent
    HTML injection (e.g. <script> or <img> tags).

    No weasyprint render needed — we assert the raw HTML output.
    """
    from api.v1.products.router import _build_pdf_html

    product_rows = [
        {
            "name": '<script>alert("xss")</script>',
            "unit": '<img src=x onerror=alert(1)>',
            "price": "$100",
            "audience_label": "Revendedores",
        },
        {
            "name": "Normal product",
            "unit": "kg",
            "price": "$50",
            "audience_label": "Revendedores",
        },
    ]

    html = _build_pdf_html(product_rows)

    # The raw script tag must NOT appear in the output
    assert '<script>alert("xss")</script>' not in html
    assert '<img src=x onerror=alert(1)>' not in html

    # The escaped versions MUST appear
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html

    # Normal product should be unchanged
    assert "<td>Normal product</td>" in html
    assert "<td>kg</td>" in html

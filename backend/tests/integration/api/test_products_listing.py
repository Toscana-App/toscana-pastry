"""Tests for GET /api/v1/products listing endpoint (T5).

Contract:
  GET /api/v1/products?audience=revendedores|consumidor_final
  Auth: require_role(ADMIN, NEGOCIO, CUSTOMER)
  Response: {"audience": str, "products": [...], "total": int}
  price_per_unit: derived via domain.pricing_service.derive_audience_price

Reglas cubiertas:
  1) unauthenticated → 401
  2) admin + revendedores → 200, base prices as strings
  3) admin + consumidor_final → 200, markup-derived prices
  4) negocio + revendedores → 200
  5) negocio + consumidor_final → 403
  6) cliente + consumidor_final → 200
  7) cliente + revendedores → 403
  8) invalid audience → 422
  9) response shape: audience + products + total consistent
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from data.db import get_db
from data.models import Base
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from domain.models import User, UserRole, Ingredient

LIST_PRODUCTS = "/api/v1/products"

_TEST_PRODUCTS = [
    {"name": "Harina 0000", "unit": "kg", "price_per_unit": "10.00", "stock_qty": "50"},
    {"name": "Azúcar refinada", "unit": "kg", "price_per_unit": "20.00", "stock_qty": "30"},
    {"name": "Manteca sin sal", "unit": "kg", "price_per_unit": "30.00", "stock_qty": "10"},
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

    # Seed users
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    await SQLUserRepository(db_session).save(
        User(email="cliente@example.com", role=UserRole.CUSTOMER)
    )
    # Seed products
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


# ─── Test 1: Unauthenticated → 401 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client):
    """T5-1: sin token → 401."""
    r = await client.get(LIST_PRODUCTS, params={"audience": "revendedores"})
    assert r.status_code == 401


# ─── Test 2: Admin + revendedores → 200, base prices ─────────────────────


@pytest.mark.asyncio
async def test_admin_revendedores_returns_base_prices(client):
    """T5-2: admin + revendedores → 200, price_per_unit = base (sin markup)."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "revendedores"
    assert data["total"] == 3
    assert len(data["products"]) == 3
    # Verify prices are strings matching base prices
    price_map = {p["name"]: p["price_per_unit"] for p in data["products"]}
    assert price_map["Harina 0000"] == "10.00"
    assert price_map["Azúcar refinada"] == "20.00"
    assert price_map["Manteca sin sal"] == "30.00"
    # Verify all price_per_unit values are strings
    for p in data["products"]:
        assert isinstance(p["price_per_unit"], str)


# ─── Test 3: Admin + consumidor_final → 200, markup-derived prices ────────


@pytest.mark.asyncio
async def test_admin_consumidor_final_returns_markup_prices(client):
    """T5-3: admin + consumidor_final → 200, precio = base × 1.40 (markup 40%).

    Base "10.00" → "14.00", "20.00" → "28.00", "30.00" → "42.00".
    """
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "consumidor_final"
    assert data["total"] == 3
    assert len(data["products"]) == 3
    price_map = {p["name"]: Decimal(p["price_per_unit"]) for p in data["products"]}
    assert price_map["Harina 0000"] == Decimal("14.00")
    assert price_map["Azúcar refinada"] == Decimal("28.00")
    assert price_map["Manteca sin sal"] == Decimal("42.00")


# ─── Test 4: Negocio + revendedores → 200 ────────────────────────────────


@pytest.mark.asyncio
async def test_negocio_revendedores_returns_200(client):
    """T5-4: negocio + revendedores → 200."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "revendedores"
    assert data["total"] == 3


# ─── Test 5: Negocio + consumidor_final → 403 ────────────────────────────


@pytest.mark.asyncio
async def test_negocio_consumidor_final_returns_403(client):
    """T5-5: negocio + consumidor_final → 403 (cross-audience forbidden)."""
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "consumidor_final" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


# ─── Test 6: Cliente + consumidor_final → 200 ────────────────────────────


@pytest.mark.asyncio
async def test_cliente_consumidor_final_returns_200(client):
    """T5-6: cliente + consumidor_final → 200."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["audience"] == "consumidor_final"
    assert data["total"] == 3


# ─── Test 7: Cliente + revendedores → 403 ────────────────────────────────


@pytest.mark.asyncio
async def test_cliente_revendedores_returns_403(client):
    """T5-7: cliente + revendedores → 403 (cross-audience forbidden)."""
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert "revendedores" in r.json()["detail"].lower() or "no puede" in r.json()["detail"].lower()


# ─── Test 8: Invalid audience → 422 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_audience_returns_422(client):
    """T5-8: audience inválida → 422 (Pydantic validation)."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# ─── Test 9: Response shape consistency ──────────────────────────────────


@pytest.mark.asyncio
async def test_response_shape_consistent(client):
    """T5-9: response tiene audience + products + total; total == len(products);
    cada producto tiene id, name, unit, price_per_unit (str), status."""
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        LIST_PRODUCTS, params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    # Top-level keys
    assert set(data.keys()) == {"audience", "products", "total"}
    assert isinstance(data["total"], int)
    assert data["total"] == len(data["products"])
    # Product shape
    required_keys = {"id", "name", "unit", "price_per_unit", "status"}
    for product in data["products"]:
        assert set(product.keys()) == required_keys, (
            f"Product keys mismatch: {set(product.keys())} vs {required_keys}"
        )
        assert isinstance(product["id"], str)
        assert isinstance(product["name"], str)
        assert isinstance(product["unit"], str)
        assert isinstance(product["price_per_unit"], str)
        assert isinstance(product["status"], str)


# ─── Optional pagination ─────────────────────────────────────────────────


async def _list(client, **params):
    token = await _token_for(client, "admin@example.com")
    return await client.get(
        LIST_PRODUCTS,
        params={"audience": "revendedores", **params},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_without_pagination_params_returns_all_rows(client):
    data = (await _list(client)).json()
    assert data["total"] == 3
    assert len(data["products"]) == 3


@pytest.mark.asyncio
async def test_pagination_returns_slice_and_full_total(client):
    first = (await _list(client, page=1, page_size=2)).json()
    second = (await _list(client, page=2, page_size=2)).json()
    assert first["total"] == second["total"] == 3
    assert len(first["products"]) == 2
    assert len(second["products"]) == 1
    ids = {p["id"] for p in first["products"]} | {p["id"] for p in second["products"]}
    assert len(ids) == 3


@pytest.mark.asyncio
async def test_page_size_only_defaults_to_first_page(client):
    data = (await _list(client, page_size=1)).json()
    assert len(data["products"]) == 1
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_invalid_pagination_returns_422(client):
    assert (await _list(client, page=0)).status_code == 422
    assert (await _list(client, page_size=501)).status_code == 422


# ─── Search by name (q, insensible a acentos, RF-P3-01) ─────────────────


@pytest.mark.asyncio
async def test_q_filters_by_name(client):
    """q=harina → solo "Harina 0000" (subcadenas en nombre)."""
    data = (await _list(client, q="harina")).json()
    assert data["total"] == 1
    assert [p["name"] for p in data["products"]] == ["Harina 0000"]


@pytest.mark.asyncio
async def test_q_is_accent_insensitive(client):
    """q=azucar → encuentra "Azúcar refinada" (accent_fold)."""
    data = (await _list(client, q="azucar")).json()
    assert data["total"] == 1
    assert [p["name"] for p in data["products"]] == ["Azúcar refinada"]


@pytest.mark.asyncio
async def test_q_without_match_returns_empty(client):
    data = (await _list(client, q="zzz-no-existe")).json()
    assert data["total"] == 0
    assert data["products"] == []


@pytest.mark.asyncio
async def test_q_with_pagination_returns_slice_and_full_total(client):
    """q que coincide en 3 insumos + page_size=2 → slice, total completo."""
    data = (await _list(client, q="a", page=1, page_size=2)).json()
    assert data["total"] == 3
    assert len(data["products"]) == 2


# ─── Búsqueda: seguridad estricta (wildcards + datos inermes) ─────────────
# El buscador es SOLO dato inerte: sin interpolación SQL (parámetros bind),
# sin metacaracteres de LIKE activos, sin invisibles/controles. (data/accent)


@pytest.mark.asyncio
async def test_q_percent_is_literal_not_wildcard(client):
    """q=% NO debe coincidir con todo: % es carácter literal, no wildcard."""
    r = await _list(client, q="%")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_underscore_is_literal_not_wildcard(client):
    """q=_ NO debe actuar como 'cualquier carácter': substring literal."""
    r = await _list(client, q="_")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_backslash_is_literal(client):
    """q=\\ es texto buscable, no introducer un escape."""
    r = await _list(client, q="\\")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_mixed_wildcards_stay_literal(client):
    """q=a%b_c → no interpreta % ni _ : cero coincidencias."""
    r = await _list(client, q="a%b_c")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_null_byte_returns_422(client):
    """NUL (categoría Cc) → 422: la búsqueda es dato inerte."""
    r = await _list(client, q="harina\x00x")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_bidi_override_returns_422(client):
    """U+202E (bidi override, Cf) → 422: no se aceptan invisibles."""
    r = await _list(client, q="harina\u202e")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_blank_returns_422(client):
    """Solo espacios → 422 (el término debe buscar algo)."""
    r = await _list(client, q="   ")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_over_max_length_returns_422(client):
    """> 120 caracteres → 422 (límite de Query)."""
    r = await _list(client, q="a" * 121)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_normal_substring_still_matches(client):
    """Regresión: la búsqueda normal (subcadena, accent-fold) sigue funcionando."""
    data = (await _list(client, q="refina")).json()
    assert data["total"] == 1
    assert [p["name"] for p in data["products"]] == ["Azúcar refinada"]

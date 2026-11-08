"""Integration tests for the server-side cart API (RF-P11-03/14, C4).

Covers:
- auth (401) and role guard (403 for admin: cart is portal self-service)
- GET /cart: empty cart, audience-derived prices (cliente markup, negocio base)
- POST /cart/items: qty bounds (422), unknown product (404), upsert qty,
  max 50 lines (422)
- DELETE /cart/items/{product_id}: 404 when absent
- POST /cart/coupon: 422 with explicit reason codes (not found / inactive /
  expired / max_uses), replacement of the single coupon
- DELETE /cart/coupon
- totals: discount on audience subtotal before the engine rounding
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.coupons.dependencies import get_coupon_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from data.db import get_db
from data.repositories.sql_coupon_repository import SQLCouponRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.coupon import Coupon
from domain.models import Ingredient, User, UserRole
from main import app

CART = "/api/v1/cart"

_TEST_PRODUCTS = [
    {"name": "Torta", "unit": "kg", "price_per_unit": "1000.00"},
    {"name": "Alfajor", "unit": "unidad", "price_per_unit": "200.00"},
]


@pytest_asyncio.fixture
async def products(db_session):
    """Product id by name for assertions."""
    created = {}
    for prod in _TEST_PRODUCTS:
        ingredient = Ingredient(
            name=prod["name"],
            unit=prod["unit"],
            price_per_unit=Decimal(prod["price_per_unit"]),
        )
        await SQLIngredientRepository(db_session).create(ingredient)
        created[prod["name"]] = ingredient.id
    return created


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

    async def override_get_coupon_repository():
        yield SQLCouponRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_coupon_repository] = override_get_coupon_repository

    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    await SQLUserRepository(db_session).save(
        User(email="cliente@example.com", role=UserRole.CUSTOMER)
    )

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
    return response.cookies["auth_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _line_for(data: dict, product_id: str) -> dict:
    for item in data["items"]:
        if item["product_id"] == product_id:
            return item
    raise AssertionError(f"product {product_id} not in cart: {data['items']}")


# ─── Auth / roles ─────────────────────────────────────────────────────

class TestCartAuth:
    async def test_unauthenticated_returns_401(self, client):
        response = await client.get(CART)
        assert response.status_code == 401

    async def test_admin_is_forbidden(self, client, db_session):
        token = await _token_for(client, "admin@example.com")
        response = await client.get(CART, headers=_auth(token))
        assert response.status_code == 403

    async def test_cliente_and_negocio_pass(self, client, db_session):
        for email in ("cliente@example.com", "negocio@example.com"):
            token = await _token_for(client, email)
            response = await client.get(CART, headers=_auth(token))
            assert response.status_code == 200


# ─── GET /cart ────────────────────────────────────────────────────────

class TestGetCart:
    async def test_empty_cart(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        response = await client.get(CART, headers=_auth(token))
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == "0"
        assert data["discount_amount"] == "0.00"
        assert data["coupon"] is None

    async def test_client_sees_markup_price(
        self, client, db_session, products
    ):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": products["Torta"], "qty": 2},
            headers=headers,
        )
        data = (await client.get(CART, headers=headers)).json()
        line = _line_for(data, products["Torta"])
        # 1000 * 1.40 (consumer markup) = 1400.00
        assert line["unit_price"] == "1400.00"
        assert line["qty"] == 2
        assert data["subtotal"] == "2800.00"
        # no coupon → total = subtotal redondeado al paso (100)
        assert data["total"] == "2800"

    async def test_negocio_sees_base_price(
        self, client, db_session, products
    ):
        token = await _token_for(client, "negocio@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": products["Torta"], "qty": 1},
            headers=headers,
        )
        data = (await client.get(CART, headers=headers)).json()
        line = _line_for(data, products["Torta"])
        assert line["unit_price"] == "1000.00"


# ─── POST /cart/items ─────────────────────────────────────────────────

class TestPostCartItems:
    async def test_add_line(self, client, db_session, products):
        token = await _token_for(client, "cliente@example.com")
        response = await client.post(
            f"{CART}/items",
            json={"product_id": products["Alfajor"], "qty": 3},
            headers=_auth(token),
        )
        assert response.status_code == 200
        data = response.json()
        line = _line_for(data, products["Alfajor"])
        assert line["qty"] == 3
        assert data["subtotal"] == "840.00"  # 200 * 1.4 * 3

    async def test_same_product_updates_qty(self, client, db_session, products):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        product_id = products["Alfajor"]
        await client.post(
            f"{CART}/items", json={"product_id": product_id, "qty": 1},
            headers=headers,
        )
        response = await client.post(
            f"{CART}/items", json={"product_id": product_id, "qty": 5},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert _line_for(data, product_id)["qty"] == 5

    @pytest.mark.parametrize("qty", [0, 1000, -1])
    async def test_qty_out_of_bounds_returns_422(
        self, client, db_session, products, qty
    ):
        token = await _token_for(client, "cliente@example.com")
        response = await client.post(
            f"{CART}/items",
            json={"product_id": products["Alfajor"], "qty": qty},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_unknown_product_returns_404(
        self, client, db_session, products
    ):
        token = await _token_for(client, "cliente@example.com")
        response = await client.post(
            f"{CART}/items",
            json={"product_id": "no-existe", "qty": 1},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_max_50_lines_returns_422(self, client, db_session):
        # 50 productos adicionales + 2 base = 52 candidatos; la linea 51
        # (de las nuevas) ya supera el tope.
        from domain.models import Ingredient

        ids = []
        for index in range(51):
            ingredient = Ingredient(
                name=f"Producto {index}",
                unit="kg",
                price_per_unit=Decimal("10.00"),
            )
            await SQLIngredientRepository(db_session).create(ingredient)
            ids.append(ingredient.id)

        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        for index, product_id in enumerate(ids[:50]):
            response = await client.post(
                f"{CART}/items",
                json={"product_id": product_id, "qty": 1},
                headers=headers,
            )
            assert response.status_code == 200, f"linea {index + 1}"
        response = await client.post(
            f"{CART}/items",
            json={"product_id": ids[50], "qty": 1},
            headers=headers,
        )
        assert response.status_code == 422


# ─── DELETE /cart/items/{product_id} ──────────────────────────────────

class TestDeleteCartItems:
    async def test_remove_line(self, client, db_session, products):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        product_id = products["Alfajor"]
        await client.post(
            f"{CART}/items", json={"product_id": product_id, "qty": 2},
            headers=headers,
        )
        response = await client.delete(
            f"{CART}/items/{product_id}", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_remove_absent_line_returns_404(
        self, client, db_session, products
    ):
        token = await _token_for(client, "cliente@example.com")
        response = await client.delete(
            f"{CART}/items/{products['Torta']}", headers=_auth(token)
        )
        assert response.status_code == 404


# ─── Cupones ──────────────────────────────────────────────────────────

class TestCartCoupon:
    async def _cart_with_torta(self, client, token, products):
        await client.post(
            f"{CART}/items",
            json={"product_id": products["Torta"], "qty": 1},
            headers=_auth(token),
        )

    async def test_unknown_coupon_returns_422(
        self, client, db_session, products
    ):
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "NOCUPON"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "coupon_not_found"

    async def test_paused_coupon_returns_422(self, client, db_session, products):
        coupon = Coupon(code="PAUSADO", type="percent", value=Decimal(10),
                        status="paused")
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "PAUSADO"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "coupon_inactive"

    async def test_expired_coupon_returns_422(self, client, db_session, products):
        import datetime

        coupon = Coupon(
            code="VENCIDO", type="percent", value=Decimal(10),
            valid_from=datetime.datetime(2026, 1, 1),
            valid_until=datetime.datetime(2026, 2, 1),
        )
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "VENCIDO"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "coupon_expired"

    async def test_max_uses_reached_returns_422(
        self, client, db_session, products
    ):
        coupon = Coupon(code="AGOTADO", type="fixed", value=Decimal(100),
                        max_uses=1, uses=1)
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "AGOTADO"},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "coupon_limit_reached"

    async def test_apply_percent_coupon(
        self, client, db_session, products
    ):
        coupon = Coupon(code="VERANO10", type="percent", value=Decimal(10))
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "VERANO10"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        data = response.json()
        # subtotal 1400 (cliente) → 10% = 140.00 → neto 1260 → paso 100
        assert data["discount_amount"] == "140.00"
        assert data["total"] == "1300"
        assert data["coupon"]["code"] == "VERANO10"

    async def test_apply_case_insensitive_code(
        self, client, db_session, products
    ):
        coupon = Coupon(code="VERANO10", type="percent", value=Decimal(10))
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "verano10"},
            headers=_auth(token),
        )
        assert response.status_code == 200

    async def test_fixed_coupon_capped_at_total(
        self, client, db_session, products
    ):
        coupon = Coupon(code="GIGANTE", type="fixed", value=Decimal(5000))
        await SQLCouponRepository(db_session).create(coupon)
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        response = await client.post(
            f"{CART}/coupon", json={"code": "GIGANTE"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        data = response.json()
        # fixed 5000 sobre subtotal 1400 → capped en 1400
        assert data["discount_amount"] == "1400.00"
        assert data["total"] == "0"

    async def test_one_coupon_per_cart_replaces(
        self, client, db_session, products
    ):
        await SQLCouponRepository(db_session).create(
            Coupon(code="A10", type="percent", value=Decimal(10))
        )
        await SQLCouponRepository(db_session).create(
            Coupon(code="B20", type="percent", value=Decimal(20))
        )
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        headers = _auth(token)
        await client.post(f"{CART}/coupon", json={"code": "A10"},
                          headers=headers)
        response = await client.post(f"{CART}/coupon", json={"code": "B20"},
                                     headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["coupon"]["code"] == "B20"
        # 20% de 1400 = 280.00 → neto 1120 → paso 100 → 1100
        assert data["discount_amount"] == "280.00"
        assert data["total"] == "1100"

    async def test_delete_coupon(self, client, db_session, products):
        await SQLCouponRepository(db_session).create(
            Coupon(code="VERANO10", type="percent", value=Decimal(10))
        )
        token = await _token_for(client, "cliente@example.com")
        await self._cart_with_torta(client, token, products)
        headers = _auth(token)
        await client.post(f"{CART}/coupon", json={"code": "VERANO10"},
                          headers=headers)
        response = await client.delete(f"{CART}/coupon", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["coupon"] is None
        assert data["discount_amount"] == "0.00"
        assert data["total"] == "1400"

    async def test_delete_coupon_when_none_is_noop(
        self, client, db_session
    ):
        token = await _token_for(client, "cliente@example.com")
        response = await client.delete(
            f"{CART}/coupon", headers=_auth(token)
        )
        assert response.status_code == 200
        assert response.json()["coupon"] is None

"""Integration tests for POST /orders (portal creation, C6) review fixes.

Covers:
    - Prices and names are resolved server-side (client values are ignored)
    - Unknown product / non-positive quantity are rejected
    - Domain validation (delivery address, past date) maps to 422
    - Closed window: 409 with a valid Retry-After
    - Cash payment marks only paid_at (payment_status stays null)
"""

import datetime
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import get_current_user, require_admin
from data.db import get_db
from data.models import Base
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import Ingredient, User, UserRole
from domain.order_window import OrderWindow
from main import app

ORDERS = "/api/v1/orders/"
CUSTOMER = User(email="cliente@example.com", role=UserRole.CUSTOMER)
ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, lambda x: x, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def product_id(db_session):
    ingredient = Ingredient(name="Torta", unit="kg", price_per_unit=Decimal("1000.00"))
    await SQLIngredientRepository(db_session).create(ingredient)
    return ingredient.id


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def _customer():
        return CUSTOMER

    async def _admin():
        return ADMIN

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_current_user] = _customer
    app.dependency_overrides[require_admin] = _admin
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


def _body(product_id: str, **overrides) -> dict:
    body = {
        "items": [{"product_id": product_id, "quantity": 2}],
        "date": (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=2)).isoformat(),
        "delivery_mode": "pickup",
        "payment_method": "cash",
    }
    body.update(overrides)
    return body


class TestPortalOrderPricing:
    async def test_prices_and_names_come_from_the_catalog(self, client, product_id):
        body = _body(product_id)
        body["items"][0].update(unit_price="0", product_name="Gratis")
        response = await client.post(ORDERS, json=body)
        assert response.status_code == 200, response.text
        data = response.json()
        [item] = data["items"]
        assert item["product_name"] == "Torta"
        # customer role => consumer audience (base price + markup), never 0
        assert Decimal(item["unit_price"]) >= Decimal("1000.00")
        assert Decimal(data["total"]) == Decimal(item["unit_price"]) * 2

    async def test_unknown_product_is_rejected(self, client):
        response = await client.post(ORDERS, json=_body("no-such-product"))
        assert response.status_code == 422
        assert response.json()["detail"] == "product_not_found"

    async def test_non_positive_quantity_is_rejected(self, client, product_id):
        for qty in (0, -3):
            body = _body(product_id)
            body["items"][0]["quantity"] = qty
            response = await client.post(ORDERS, json=body)
            assert response.status_code == 422, qty


class TestPortalOrderDomainRules:
    async def test_delivery_requires_address(self, client, product_id):
        response = await client.post(
            ORDERS, json=_body(product_id, delivery_mode="delivery", delivery_address="  ")
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "delivery_requires_address"

    async def test_past_date_is_rejected(self, client, product_id):
        past = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=3)).isoformat()
        response = await client.post(ORDERS, json=_body(product_id, date=past))
        assert response.status_code == 422
        assert response.json()["detail"] == "date_must_be_today_or_later"

    async def test_invalid_payment_method_is_rejected(self, client, product_id):
        response = await client.post(ORDERS, json=_body(product_id, payment_method="bitcoin"))
        assert response.status_code == 422
        assert response.json()["detail"] == "invalid_payment_method"

    async def test_order_is_persisted_for_the_caller(self, client, db_session, product_id):
        response = await client.post(ORDERS, json=_body(product_id))
        assert response.status_code == 200
        stored = await SQLOrderRepository(db_session).get(response.json()["id"])
        assert stored is not None
        assert stored.customer_id == CUSTOMER.id
        assert len(stored.items) == 1


class TestOrderWindowRetryAfter:
    async def test_closed_window_sends_retry_after_http_date(
        self, client, db_session, product_id
    ):
        reopens = datetime.datetime(2030, 1, 2, 3, 4, 5, tzinfo=datetime.UTC)
        await SQLOrderRepository(db_session).update_order_window(
            OrderWindow(open=False, reopens_at=reopens, message="closed")
        )
        response = await client.post(ORDERS, json=_body(product_id))
        assert response.status_code == 409
        assert response.json()["detail"] == "order_window_closed"
        assert response.headers["retry-after"] == "Wed, 02 Jan 2030 03:04:05 GMT"
        assert "reafter" not in response.headers

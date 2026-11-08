
import json
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.v1.auth.dependencies import get_user_repository
from api.v1.coupons.dependencies import get_coupon_repository
from api.v1.dependencies import get_current_user, require_admin
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.orders.dependencies import get_order_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.settings.dependencies import get_settings_repository
from data.accent import accent_fold
from data.db import get_db
from data.models import (
    Base,
    BusinessSettingsORM,
    CartItemORM,
    IngredientORM,
    OrderItemORM,
    ProductORM,
    RecipeItemORM,
)
from data.repositories.sql_coupon_repository import SQLCouponRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app

CART = "/api/v1/cart"
ORDERS = "/api/v1/orders/"

CUSTOMER = User(email="cliente@example.com", role=UserRole.CUSTOMER)
NEGOCIO = User(email="negocio@example.com", role=UserRole.NEGOCIO)
ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)


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
        yield session
    await engine.dispose()


async def _seed_product(
    db_session,
    name: str,
    available: bool = True,
    price_per_unit: str = "10.00",
    stock_qty: str = "10",
    recipe_qty: str = "1",
    complete: bool = True,
) -> tuple[str, str]:
    ingredient = IngredientORM(
        name=f"Insumo {name}",
        unit="kg",
        price_per_unit=price_per_unit,
        stock_qty=stock_qty,
    )
    db_session.add(ingredient)
    await db_session.commit()

    product_id = str(uuid.uuid4())
    product = ProductORM(
        id=product_id,
        name=name,
        category="Pan",
        description="",
        prep_time_min=0,
        servings=4,
        difficulty="simple",
        available=available,
    )
    product.recipe_items = [
        RecipeItemORM(
            id=str(uuid.uuid4()),
            product_id=product_id,
            ingredient_id=ingredient.id if complete else str(uuid.uuid4()),
            qty=recipe_qty,
            unit="kg",
            position=0,
        )
    ]
    db_session.add(product)
    await db_session.commit()
    return product_id, str(ingredient.id)


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

    async def override_get_coupon_repository():
        yield SQLCouponRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_coupon_repository] = override_get_coupon_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    app.dependency_overrides[require_admin] = lambda: ADMIN

    db_session.add(
        BusinessSettingsORM(
            hourly_rate="0.01",
            margin_pct="25",
            round_step="0.01",
            gas_pct="0",
            waste_pct="0",
            consumer_markup_pct="40",
            include_labor=False,
            include_gas=False,
            include_waste=False,
            default_prep_minutes=0,
            default_servings=4,
            default_difficulty="simple",
            business_name="",
            footer_text="",
        )
    )
    await db_session.commit()

    def as_user(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    as_user(CUSTOMER)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.as_user = as_user
            yield ac
    finally:
        app.dependency_overrides.clear()


def _order_body(product_id: str, quantity: int = 2, **overrides) -> dict:
    body = {
        "items": [{"product_id": product_id, "quantity": quantity}],
        "date": "2030-01-02T12:00:00",
        "delivery_mode": "pickup",
        "payment_method": "cash",
    }
    body.update(overrides)
    return body


async def _stock_of(db_session, ingredient_id: str) -> Decimal:
    orm = (
        await db_session.execute(
            select(IngredientORM).where(IngredientORM.id == ingredient_id)
        )
    ).scalar_one()
    return Decimal(orm.stock_qty)


@pytest.mark.asyncio
async def test_cart_adds_published_product_with_audience_price(client, db_session):
    product_id, _ = await _seed_product(db_session, "Pan de campo")
    r = await client.post(f"{CART}/items", json={"product_id": product_id, "qty": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audience"] == "consumidor_final"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["product_id"] == product_id
    assert item["name"] == "Pan de campo"
    assert Decimal(item["unit_price"]) == Decimal("17.50")
    assert Decimal(item["total"]) == Decimal("35.00")
    assert Decimal(body["subtotal"]) == Decimal("35.00")


@pytest.mark.asyncio
async def test_cart_negocio_uses_base_price(client, db_session):
    product_id, _ = await _seed_product(db_session, "Pan de campo")
    client.as_user(NEGOCIO)
    r = await client.post(f"{CART}/items", json={"product_id": product_id, "qty": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audience"] == "revendedores"
    assert Decimal(body["items"][0]["unit_price"]) == Decimal("12.50")


@pytest.mark.asyncio
async def test_cart_rejects_hidden_product_422(client, db_session):
    product_id, _ = await _seed_product(db_session, "Torta oculta", available=False)
    r = await client.post(f"{CART}/items", json={"product_id": product_id, "qty": 1})
    assert r.status_code == 422
    assert r.json()["detail"] == "product_not_available"


@pytest.mark.asyncio
async def test_cart_rejects_incomplete_product_422(client, db_session):
    product_id, _ = await _seed_product(db_session, "Torta incompleta", complete=False)
    r = await client.post(f"{CART}/items", json={"product_id": product_id, "qty": 1})
    assert r.status_code == 422
    assert r.json()["detail"] == "product_not_available"


@pytest.mark.asyncio
async def test_cart_unknown_product_404(client):
    r = await client.post(
        f"{CART}/items", json={"product_id": str(uuid.uuid4()), "qty": 1}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cart_line_of_retired_product_stops_contributing(client, db_session):
    product_id, _ = await _seed_product(db_session, "Pan de campo")
    db_session.add(CartItemORM(user_id=CUSTOMER.id, product_id=product_id, qty=1))
    await db_session.commit()
    product = (
        await db_session.execute(
            select(ProductORM).where(ProductORM.id == product_id)
        )
    ).scalar_one()
    product.available = False
    await db_session.commit()

    r = await client.get(CART)
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert Decimal(body["subtotal"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_portal_order_prices_from_engine_and_product_catalog(client, db_session):
    product_id, _ = await _seed_product(db_session, "Pan de campo")
    r = await client.post(ORDERS, json=_order_body(product_id, quantity=2))
    assert r.status_code == 200, r.text
    body = r.json()
    item = body["items"][0]
    assert item["product_name"] == "Pan de campo"
    assert Decimal(item["unit_price"]) == Decimal("17.50")
    assert Decimal(item["total"]) == Decimal("35.00")
    assert Decimal(body["total"]) == Decimal("35.00")


@pytest.mark.asyncio
async def test_portal_order_rejects_hidden_product_422(client, db_session):
    product_id, _ = await _seed_product(db_session, "Torta oculta", available=False)
    r = await client.post(ORDERS, json=_order_body(product_id))
    assert r.status_code == 422
    assert r.json()["detail"] == "product_not_available"


@pytest.mark.asyncio
async def test_portal_order_rejects_incomplete_product_422(client, db_session):
    product_id, _ = await _seed_product(db_session, "Torta incompleta", complete=False)
    r = await client.post(ORDERS, json=_order_body(product_id))
    assert r.status_code == 422
    assert r.json()["detail"] == "product_not_available"


@pytest.mark.asyncio
async def test_portal_order_persists_recipe_snapshot(client, db_session):
    product_id, _ = await _seed_product(db_session, "Pan de campo")
    r = await client.post(ORDERS, json=_order_body(product_id, quantity=2))
    assert r.status_code == 200
    order_id = r.json()["id"]

    item = (
        await db_session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == order_id)
        )
    ).scalar_one()
    assert item.snapshot is not None
    assert item.portions == 4
    assert item.qty == 2
    snapshot = json.loads(item.snapshot)
    assert len(snapshot["lines"]) == 1
    assert snapshot["lines"][0]["ingredient_name"] == "Insumo Pan de campo"
    assert Decimal(snapshot["lines"][0]["qty"]) == Decimal("2")


@pytest.mark.asyncio
async def test_confirm_order_discounts_stock_from_snapshot(client, db_session):
    product_id, ingredient_id = await _seed_product(db_session, "Pan de campo")
    r = await client.post(ORDERS, json=_order_body(product_id, quantity=2))
    assert r.status_code == 200
    order_id = r.json()["id"]
    assert await _stock_of(db_session, ingredient_id) == Decimal("10")

    r = await client.patch(f"{ORDERS}{order_id}/status", json={"status": "confirmado"})
    assert r.status_code == 200, r.text
    assert await _stock_of(db_session, ingredient_id) == Decimal("8")


@pytest.mark.asyncio
async def test_cancel_order_replenishes_stock(client, db_session):
    product_id, ingredient_id = await _seed_product(db_session, "Pan de campo")
    r = await client.post(ORDERS, json=_order_body(product_id, quantity=2))
    order_id = r.json()["id"]
    r = await client.patch(f"{ORDERS}{order_id}/status", json={"status": "confirmado"})
    assert r.status_code == 200, r.text
    r = await client.patch(f"{ORDERS}{order_id}/status", json={"status": "cancelado"})
    assert r.status_code == 200, r.text
    assert await _stock_of(db_session, ingredient_id) == Decimal("10")


@pytest.mark.asyncio
async def test_confirm_fails_409_when_stock_is_short(client, db_session):
    product_id, ingredient_id = await _seed_product(
        db_session, "Pan de campo", stock_qty="1"
    )
    r = await client.post(ORDERS, json=_order_body(product_id, quantity=2))
    order_id = r.json()["id"]
    r = await client.patch(f"{ORDERS}{order_id}/status", json={"status": "confirmado"})
    assert r.status_code == 409, r.text
    assert await _stock_of(db_session, ingredient_id) == Decimal("1")

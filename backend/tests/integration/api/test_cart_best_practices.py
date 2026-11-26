import datetime
import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.v1.auth.dependencies import get_user_repository
from api.v1.cart.dependencies import get_cart_repository
from api.v1.coupons.dependencies import get_coupon_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.orders.dependencies import get_order_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.settings.dependencies import get_settings_repository
from data.db import get_db
from data.models import (
    BusinessSettingsORM,
    CartItemORM,
    CouponORM,
    IngredientORM,
    ProductORM,
    RecipeItemORM,
)
from data.repositories.sql_cart_repository import SQLCartRepository
from data.repositories.sql_coupon_repository import SQLCouponRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.coupon import Coupon
from domain.models import User, UserRole
from main import app

try:
    from domain.cart import CART_TTL_DAYS
except ImportError:
    CART_TTL_DAYS = 30

CART = "/api/v1/cart"
ORDERS = "/api/v1/orders/"


@pytest_asyncio.fixture
async def products(db_session):
    ingredient = IngredientORM(
        id="ing-harina",
        name="Harina",
        unit="kg",
        price_per_unit="1000.00",
        stock_qty="100",
    )
    db_session.add(ingredient)
    await db_session.commit()
    product = ProductORM(
        id="prod-torta",
        name="Torta",
        category="General",
        description="",
        prep_time_min=0,
        servings=1,
        difficulty="simple",
        available=True,
    )
    product.recipe_items = [
        RecipeItemORM(
            id=str(uuid.uuid4()),
            product_id="prod-torta",
            ingredient_id="ing-harina",
            qty="1",
            unit="kg",
            position=0,
        )
    ]
    db_session.add(product)
    await db_session.commit()
    return {"Torta": "prod-torta"}


@pytest_asyncio.fixture
async def client(db_session, products):
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

    async def override_get_cart_repository():
        yield SQLCartRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_coupon_repository] = override_get_coupon_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    app.dependency_overrides[get_cart_repository] = override_get_cart_repository

    db_session.add(
        BusinessSettingsORM(
            hourly_rate="0.01",
            margin_pct="0",
            round_step="100",
            gas_pct="0",
            waste_pct="0",
            consumer_markup_pct="40",
            include_labor=False,
            include_gas=False,
            include_waste=False,
            default_prep_minutes=0,
            default_servings=1,
            default_difficulty="simple",
            business_name="",
            footer_text="",
        )
    )
    await db_session.commit()

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


def _order_body(quantity=1, coupon_code=None):
    body = {
        "items": [{"product_id": "prod-torta", "quantity": quantity}],
        "date": datetime.datetime.now(datetime.UTC).isoformat(),
        "payment_method": "cash",
        "delivery_mode": "delivery",
        "delivery_address": "Av. Belgrano 100",
        "phone": "+5493541000001",
    }
    if coupon_code:
        body["coupon_code"] = coupon_code
    return body


async def _set_ingredient_stock(db_session, stock: str) -> None:
    ing = (
        await db_session.execute(
            select(IngredientORM).where(IngredientORM.id == "ing-harina")
        )
    ).scalar_one()
    ing.stock_qty = stock
    await db_session.commit()


async def _set_product_available(db_session, available: bool) -> None:
    prod = (
        await db_session.execute(
            select(ProductORM).where(ProductORM.id == "prod-torta")
        )
    ).scalar_one()
    prod.available = available
    await db_session.commit()




class TestCouponAtCheckout:
    async def test_order_applies_coupon_discount(self, client, db_session):
        await SQLCouponRepository(db_session).create(
            Coupon(code="VERANO10", type="percent", value=Decimal(10))
        )
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        res = await client.post(
            f"{CART}/coupon", json={"code": "VERANO10"}, headers=headers
        )
        assert res.status_code == 200, res.text
        cart_total = Decimal(res.json()["total"])
        assert cart_total < Decimal("1400"), (
            "sanity: el carrito ya aplica el descuento"
        )

        res = await client.post(
            ORDERS,
            json=_order_body(1, coupon_code="VERANO10"),
            headers={**headers, "Idempotency-Key": "k-coupon-1"},
        )
        assert res.status_code in (200, 201), res.text
        order = res.json()
        gross = Decimal(order["total"])
        assert order["discount_amount"] is not None
        assert Decimal(order["discount_amount"]) == gross - cart_total
        assert gross - Decimal(order["discount_amount"]) == cart_total

    async def test_coupon_uses_incremented_once_per_order(
        self, client, db_session
    ):
        await SQLCouponRepository(db_session).create(
            Coupon(code="VERANO10", type="percent", value=Decimal(10))
        )
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        body = _order_body(1, coupon_code="VERANO10")

        res = await client.post(
            ORDERS,
            json=body,
            headers={**headers, "Idempotency-Key": "k-coupon-2"},
        )
        assert res.status_code in (200, 201), res.text
        order_id = res.json()["id"]

        res2 = await client.post(
            ORDERS,
            json=body,
            headers={**headers, "Idempotency-Key": "k-coupon-2"},
        )
        assert res2.status_code in (200, 201)
        assert res2.json()["id"] == order_id

        uses = (
            await db_session.execute(
                select(CouponORM.uses).where(CouponORM.code == "VERANO10")
            )
        ).scalar_one()
        assert uses == 1

    async def test_expired_coupon_rejected_at_checkout(self, client, db_session):
        await SQLCouponRepository(db_session).create(
            Coupon(
                code="VENCIDO",
                type="percent",
                value=Decimal(10),
                valid_from=datetime.datetime(2026, 1, 1),
                valid_until=datetime.datetime(2026, 2, 1),
            )
        )
        token = await _token_for(client, "cliente@example.com")
        res = await client.post(
            ORDERS,
            json=_order_body(1, coupon_code="VENCIDO"),
            headers={**_auth(token), "Idempotency-Key": "k-coupon-3"},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "coupon_expired"

    async def test_coupon_limit_reached_rejected_at_checkout(
        self, client, db_session
    ):
        await SQLCouponRepository(db_session).create(
            Coupon(code="AGOTADO", type="fixed", value=Decimal(100),
                   max_uses=1, uses=1)
        )
        token = await _token_for(client, "cliente@example.com")
        res = await client.post(
            ORDERS,
            json=_order_body(1, coupon_code="AGOTADO"),
            headers={**_auth(token), "Idempotency-Key": "k-coupon-4"},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "coupon_limit_reached"

    async def test_unknown_coupon_rejected_at_checkout(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        res = await client.post(
            ORDERS,
            json=_order_body(1, coupon_code="NOEXISTE1"),
            headers={**_auth(token), "Idempotency-Key": "k-coupon-5"},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "coupon_not_found"




class TestCartCouponValidation:
    async def test_apply_coupon_rejects_limit_reached(
        self, client, db_session
    ):
        await SQLCouponRepository(db_session).create(
            Coupon(code="VERANO10", type="percent", value=Decimal(10))
        )
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        res = await client.post(
            f"{CART}/coupon", json={"code": "VERANO10"}, headers=headers
        )
        assert res.status_code == 200
        coupon = (
            await db_session.execute(
                select(CouponORM).where(CouponORM.code == "VERANO10")
            )
        ).scalar_one()
        coupon.uses = 5
        coupon.max_uses = 5
        await db_session.commit()

        cart = (await client.get(CART, headers=headers)).json()
        assert cart["coupon"] is None
        assert cart["discount_amount"] == "0.00"
        assert cart["total"] == "1400"




class TestCartLineAvailability:
    async def test_unavailable_product_flagged_and_excluded_from_total(
        self, client, db_session
    ):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 2},
            headers=headers,
        )
        await _set_product_available(db_session, False)

        cart = (await client.get(CART, headers=headers)).json()
        assert len(cart["items"]) == 1
        item = cart["items"][0]
        assert item["available"] is False
        assert item["issue"] == "product_not_available"
        assert cart["total"] == "0"
        assert cart["discount_amount"] == "0.00"

    async def test_deleted_product_line_removed(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        prod = (
            await db_session.execute(
                select(ProductORM).where(ProductORM.id == "prod-torta")
            )
        ).scalar_one()
        await db_session.delete(prod)
        await db_session.commit()

        cart = (await client.get(CART, headers=headers)).json()
        assert cart["items"] == []
        assert cart["total"] == "0"

    async def test_out_of_stock_line_flagged(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        await _set_ingredient_stock(db_session, "0")

        cart = (await client.get(CART, headers=headers)).json()
        item = cart["items"][0]
        assert item["available"] is False
        assert item["issue"] == "out_of_stock"
        assert cart["total"] == "0"

    async def test_portal_order_rejects_out_of_stock(self, client, db_session):
        await _set_ingredient_stock(db_session, "0")
        token = await _token_for(client, "cliente@example.com")
        res = await client.post(
            ORDERS,
            json=_order_body(1),
            headers={**_auth(token), "Idempotency-Key": "k-stock-1"},
        )
        assert res.status_code == 422
        assert res.json()["detail"] == "out_of_stock"




class TestCartTtl:
    async def test_stale_line_pruned_on_read(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        item = (
            await db_session.execute(select(CartItemORM))
        ).scalar_one()
        item.updated_at = (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=CART_TTL_DAYS + 1)
        )
        await db_session.commit()

        cart = (await client.get(CART, headers=headers)).json()
        assert cart["items"] == []

    async def test_recent_line_kept(self, client, db_session):
        token = await _token_for(client, "cliente@example.com")
        headers = _auth(token)
        await client.post(
            f"{CART}/items",
            json={"product_id": "prod-torta", "qty": 1},
            headers=headers,
        )
        item = (
            await db_session.execute(select(CartItemORM))
        ).scalar_one()
        item.updated_at = (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=10)
        )
        await db_session.commit()

        cart = (await client.get(CART, headers=headers)).json()
        assert len(cart["items"]) == 1

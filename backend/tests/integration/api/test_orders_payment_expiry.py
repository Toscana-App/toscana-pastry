"""Lazy 24 h expiry of pending payments: repo method + endpoints (fake clock)."""

import datetime
import uuid
from decimal import Decimal

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.v1.dependencies import get_current_user
from api.v1.orders.dependencies import get_checkout_provider, get_now
from data.accent import accent_fold
from data.db import get_db as get_db_orig
from data.models import Base, CouponORM, OrderORM
from data.payments.mercadopago import MercadoPagoCheckoutProvider
from data.repositories.sql_order_repository import SQLOrderRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, OrderStatus, PaymentMethod, PaymentStatus
from main import app

T0 = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)
_CLOCK = {"now": T0}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fns(dbapi_connection, connection_record):
        dbapi_connection.create_function("accent_fold", 1, accent_fold, deterministic=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


def _provider():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "pref", "init_point": "https://mp/x"})

    return MercadoPagoCheckoutProvider(
        access_token="APP_USR-t", webhook_secret="s", transport=httpx.MockTransport(handler)
    )


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session

    async def _repo():
        yield SQLOrderRepository(db_session)

    from api.v1.orders.dependencies import get_order_repository

    _CLOCK["now"] = T0
    app.dependency_overrides[get_db_orig] = _db
    app.dependency_overrides[get_order_repository] = _repo
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_checkout_provider] = _provider
    app.dependency_overrides[get_now] = lambda: _CLOCK["now"]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


async def _pending_order(db_session, coupon_code: str | None = None) -> Order:
    order = Order(
        customer_id=str(uuid.uuid4()),
        date=T0,
        items=[OrderItem("p", "Torta", 1, Decimal(1000))],
        payment_method=PaymentMethod.MERCADOPAGO,
        payment_status=PaymentStatus.PENDING,
        coupon_code=coupon_code,
        created_at=T0,
    )
    await SQLOrderRepository(db_session).create(order)
    await db_session.commit()
    return order


async def _coupon(db_session, uses: int) -> None:
    db_session.add(CouponORM(id="c1", code="PROMO", code_key="promo", type="percent", value="10", uses=uses))
    await db_session.commit()


async def _coupon_row(db_session) -> CouponORM:
    db_session.expire_all()
    return (await db_session.execute(select(CouponORM))).scalar_one()


async def _row(db_session, order_id: str) -> OrderORM:
    db_session.expire_all()
    return (await db_session.execute(select(OrderORM).where(OrderORM.id == order_id))).scalar_one()


async def test_repo_expire_cancels_order_and_releases_coupon_use(db_session):
    await _coupon(db_session, uses=2)
    order = await _pending_order(db_session, "PROMO")

    assert await SQLOrderRepository(db_session).expire_pending_payment(order.id) is True

    row = await _row(db_session, order.id)
    assert row.status == OrderStatus.CANCELADO
    assert row.payment_status == PaymentStatus.FAILED
    coupon = await _coupon_row(db_session)
    assert coupon.uses == 1


async def test_repo_expire_is_noop_when_already_paid(db_session):
    await _coupon(db_session, uses=1)
    order = await _pending_order(db_session, "PROMO")
    repo = SQLOrderRepository(db_session)
    await repo.apply_payment_event("p1:approved", order.id, "p1", PaymentStatus.APPROVED, T0)

    assert await repo.expire_pending_payment(order.id) is False
    assert (await _row(db_session, order.id)).status == OrderStatus.NUEVO
    assert (await _coupon_row(db_session)).uses == 1


async def test_get_payment_before_24h_keeps_order(client, db_session):
    order = await _pending_order(db_session)
    _CLOCK["now"] = T0 + datetime.timedelta(hours=23, minutes=59)

    resp = await client.get(f"/api/v1/orders/{order.id}/payment")

    assert resp.json()["status"] == "pending"
    assert (await _row(db_session, order.id)).status == OrderStatus.NUEVO


async def test_get_payment_after_24h_cancels_order_and_releases_coupon(client, db_session):
    await _coupon(db_session, uses=1)
    order = await _pending_order(db_session, "PROMO")
    _CLOCK["now"] = T0 + datetime.timedelta(hours=24)

    resp = await client.get(f"/api/v1/orders/{order.id}/payment")

    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["paid"] is False
    assert (await _row(db_session, order.id)).status == OrderStatus.CANCELADO
    assert (await _coupon_row(db_session)).uses == 0


async def test_initiating_payment_on_expired_order_cancels_it(client, db_session):
    order = await _pending_order(db_session)
    _CLOCK["now"] = T0 + datetime.timedelta(hours=25)

    resp = await client.post(
        f"/api/v1/orders/{order.id}/payment", headers={"Idempotency-Key": "k1"}
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "order_not_payable"
    assert (await _row(db_session, order.id)).status == OrderStatus.CANCELADO

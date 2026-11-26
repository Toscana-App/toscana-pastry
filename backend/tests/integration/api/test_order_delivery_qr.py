import datetime
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.dependencies import get_current_user
from data.db import get_db as get_db_orig
from data.models import Base, OrderDeliveryLinkORM, OrderItemORM, OrderORM
from domain.delivery import DeliveryLinkState, delivery_url
from domain.models import User, UserRole
from main import app

ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)
CUSTOMER = User(email="customer@example.com", role=UserRole.CUSTOMER)

_CURRENT = {"user": ADMIN}
_SEQ = {"n": 0}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
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


async def _admin_user():
    return ADMIN


async def _current_user():
    return _CURRENT["user"]


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    _CURRENT["user"] = ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


async def _add_order(
    db_session, status="confirmed", order_id=None, items=None
) -> OrderORM:
    _SEQ["n"] += 1
    order = OrderORM(
        id=order_id or str(uuid.uuid4()),
        customer_id="c1",
        code=f"#0000{_SEQ['n']}",
        status=status,
        date=datetime.datetime.now(datetime.UTC),
        payment_method="cash",
        delivery_mode="pickup",
        delivery_address="",
        customer_name="Ana",
        customer_phone="123",
        created_at=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(order)
    for position, (name, quantity) in enumerate(items or ()):
        db_session.add(
            OrderItemORM(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=f"p{position}",
                product_name=name,
                quantity=quantity,
                unit_price="1.00",
                portions=1,
                position=position,
            )
        )
    await db_session.commit()
    return order


async def _issue(client, order_id):
    return await client.get(f"/api/v1/orders/{order_id}/delivery-link")


async def test_q1_issues_a_uuid4_link(client, db_session):
    order = await _add_order(db_session)

    response = await _issue(client, order.id)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "active"
    assert uuid.UUID(body["token"]).version == 4
    assert body["url"] == delivery_url("http://localhost:3000", body["token"])


async def test_q2_issue_is_idempotent(client, db_session):
    order = await _add_order(db_session)

    first = (await _issue(client, order.id)).json()
    second = (await _issue(client, order.id)).json()

    assert first["token"] == second["token"]


async def test_q3_qr_is_a_svg_document(client, db_session):
    order = await _add_order(db_session)

    response = await client.get(f"/api/v1/orders/{order.id}/delivery-qr.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.text.startswith("<svg")


async def test_q4_terminal_order_does_not_issue_a_link(client, db_session):
    order = await _add_order(db_session, status="delivered")

    response = await _issue(client, order.id)

    assert response.status_code == 409
    assert response.json()["detail"] == "order_not_deliverable"


async def test_q5_delivery_revokes_the_link(client, db_session):
    order = await _add_order(db_session, status="pending_delivery")
    token = (await _issue(client, order.id)).json()["token"]

    response = await client.patch(
        f"/api/v1/orders/{order.id}/status", json={"status": "delivered"}
    )
    assert response.status_code == 200

    row = (
        await db_session.execute(
            select(OrderDeliveryLinkORM).where(OrderDeliveryLinkORM.token == token)
        )
    ).scalar_one()
    assert row.revoked_at is not None
    assert row.revoked_reason == "delivered"

    public = await client.get(f"/api/v1/public/orders/{token}")
    assert public.json()["state"] == "delivered"


async def test_q5b_cancellation_revokes_with_cancelled_reason(client, db_session):
    order = await _add_order(db_session)
    token = (await _issue(client, order.id)).json()["token"]

    response = await client.patch(
        f"/api/v1/orders/{order.id}/status", json={"status": "cancelled"}
    )
    assert response.status_code == 200

    row = (
        await db_session.execute(
            select(OrderDeliveryLinkORM).where(OrderDeliveryLinkORM.token == token)
        )
    ).scalar_one()
    assert row.revoked_reason == "cancelled"
    assert (await client.get(f"/api/v1/public/orders/{token}")).json()["state"] == (
        "cancelled"
    )


async def test_q7_public_view_of_active_order(client, db_session):
    order = await _add_order(db_session, status="pending_delivery")
    token = (await _issue(client, order.id)).json()["token"]

    response = await client.get(f"/api/v1/public/orders/{token}")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "active"
    assert body["order_code"] == order.code
    assert body["status"] == "pending_delivery"
    assert body["status_label"] == "Pendiente entrega"


async def test_q8_public_view_says_delivered(client, db_session):
    order = await _add_order(db_session)
    token = (await _issue(client, order.id)).json()["token"]
    await db_session.execute(
        select(OrderORM).where(OrderORM.id == order.id)
    )
    order.status = "delivered"
    await db_session.commit()

    body = (await client.get(f"/api/v1/public/orders/{token}")).json()

    assert body["state"] == "delivered"
    assert body["message"] == "Su pedido ha sido entregado"


async def test_q10_unknown_and_malformed_tokens_are_404(client):
    unknown = await client.get(f"/api/v1/public/orders/{uuid.uuid4()}")
    malformed = await client.get("/api/v1/public/orders/no-es-uuid")

    assert unknown.status_code == 404
    assert malformed.status_code == 404
    assert unknown.json()["detail"] == "Link inválido o expirado"


async def test_q11_stale_active_link_never_exposes_in_progress_data(
    client, db_session
):
    order = await _add_order(db_session, status="delivered")
    token = str(uuid.uuid4())
    db_session.add(
        OrderDeliveryLinkORM(
            token=token,
            order_id=order.id,
            created_at=datetime.datetime.now(datetime.UTC),
        )
    )
    await db_session.commit()

    body = (await client.get(f"/api/v1/public/orders/{token}")).json()

    assert body["state"] == "delivered"
    assert body["status"] == "delivered"
    assert "customer" not in body and "total" not in body


async def test_q12_customer_cannot_issue_link(client, db_session):
    order = await _add_order(db_session)
    _CURRENT["user"] = CUSTOMER

    response = await _issue(client, order.id)

    assert response.status_code == 403


async def test_q13_unknown_order_is_404(client):
    response = await _issue(client, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == "Pedido no encontrado"


async def test_q14_public_view_includes_item_descriptions(client, db_session):
    order = await _add_order(
        db_session,
        status="pending_delivery",
        items=[("Cheesecake", 2), ("Brownie de nuez", 1)],
    )
    token = (await _issue(client, order.id)).json()["token"]

    body = (await client.get(f"/api/v1/public/orders/{token}")).json()

    assert body["items"] == [
        {"name": "Cheesecake", "quantity": 2},
        {"name": "Brownie de nuez", "quantity": 1},
    ]


async def test_q15_expired_link_hides_item_descriptions(client, db_session):
    order = await _add_order(
        db_session, status="confirmed", items=[("Cheesecake", 2)]
    )
    token = str(uuid.uuid4())
    db_session.add(
        OrderDeliveryLinkORM(
            token=token,
            order_id=order.id,
            created_at=datetime.datetime.now(datetime.UTC),
            revoked_at=datetime.datetime.now(datetime.UTC),
            revoked_reason="delivered",
        )
    )
    await db_session.commit()

    body = (await client.get(f"/api/v1/public/orders/{token}")).json()

    assert body["state"] == "expired"
    assert body["items"] == []


async def test_public_payload_has_no_pii_and_is_not_cacheable(client, db_session):
    order = await _add_order(
        db_session, items=[("Cheesecake", 2)]
    )
    token = (await _issue(client, order.id)).json()["token"]

    response = await client.get(f"/api/v1/public/orders/{token}")

    assert set(response.json()) == {
        "state",
        "order_code",
        "status",
        "status_label",
        "message",
        "items",
    }
    assert "Ana" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == "noindex"


async def test_only_one_active_link_per_order_is_enforced_by_the_database(
    db_session,
):
    order = await _add_order(db_session)
    db_session.add(
        OrderDeliveryLinkORM(
            token=str(uuid.uuid4()),
            order_id=order.id,
            created_at=datetime.datetime.now(datetime.UTC),
        )
    )
    await db_session.commit()

    db_session.add(
        OrderDeliveryLinkORM(
            token=str(uuid.uuid4()),
            order_id=order.id,
            created_at=datetime.datetime.now(datetime.UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


def test_state_enum_is_the_contract():
    assert [s.value for s in DeliveryLinkState] == [
        "active",
        "delivered",
        "cancelled",
        "expired",
    ]

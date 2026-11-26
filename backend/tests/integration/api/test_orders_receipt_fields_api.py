import datetime
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import get_current_user, require_admin
from api.v1.invoicing.dependencies import get_invoice_repository
from data.db import get_db as get_db_orig
from data.models import OrderORM
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod
from main import app

CUSTOMER = User(email="cliente@example.com", role=UserRole.CUSTOMER)
ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_invoice_repository():
        yield SQLInvoiceRepository(db_session)

    async def override_get_order_repo():
        yield SQLOrderRepository(db_session)

    async def _customer():
        return CUSTOMER

    async def _admin():
        return ADMIN

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_invoice_repository] = override_get_invoice_repository
    app.dependency_overrides[SQLOrderRepository] = override_get_order_repo
    app.dependency_overrides[get_current_user] = _customer
    app.dependency_overrides[require_admin] = _admin

    await SQLUserRepository(db_session).save(ADMIN)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


def _transfer_order(customer_id: str) -> Order:
    return Order(
        customer_id=customer_id,
        customer_name=CUSTOMER.email,
        customer_phone="11555555555",
        date=datetime.datetime.now(datetime.UTC),
        items=[
            OrderItem(
                product_id="p1",
                product_name="Torta",
                quantity=1,
                unit_price=Decimal("1000"),
            )
        ],
        payment_method=PaymentMethod.TRANSFER,
    )


@pytest_asyncio.fixture
async def transfer_order(db_session):
    order = _transfer_order(CUSTOMER.id)
    await SQLOrderRepository(db_session).create(order)
    return order


async def _seed_receipt(
    db_session, order_id: str, *, viewed: bool = True
) -> datetime.datetime:
    now = datetime.datetime.now(datetime.UTC)
    orm = await db_session.get(OrderORM, order_id)
    orm.receipt_file = f"{order_id}.jpg"
    orm.receipt_content_type = "image/jpeg"
    orm.receipt_size_bytes = 2048
    orm.receipt_uploaded_at = now
    orm.receipt_viewed_at = now if viewed else None
    await db_session.commit()
    return now


class TestPortalReceiptFields:

    async def test_detail_without_receipt_returns_defaults(
        self, client, transfer_order
    ):
        response = await client.get(f"/api/v1/orders/mine/{transfer_order.code}")
        assert response.status_code == 200
        data = response.json()
        assert data["receipt_uploaded"] is False
        assert data["receipt_content_type"] is None
        assert data["receipt_uploaded_at"] is None
        assert data["receipt_viewed_at"] is None

    async def test_detail_with_receipt_returns_fields(
        self, client, db_session, transfer_order
    ):
        await _seed_receipt(db_session, transfer_order.id)
        response = await client.get(f"/api/v1/orders/mine/{transfer_order.code}")
        assert response.status_code == 200
        data = response.json()
        assert data["receipt_uploaded"] is True
        assert data["receipt_content_type"] == "image/jpeg"
        assert data["receipt_uploaded_at"] is not None
        assert data["receipt_viewed_at"] is not None

    async def test_list_includes_receipt_fields(self, client, transfer_order):
        response = await client.get("/api/v1/orders/mine")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        item = data["orders"][0]
        assert item["receipt_uploaded"] is False
        assert item["receipt_content_type"] is None
        assert item["receipt_uploaded_at"] is None
        assert item["receipt_viewed_at"] is None


class TestAdminReceiptFields:

    async def test_list_includes_receipt_fields(self, client, transfer_order):
        response = await client.get("/api/v1/orders")
        assert response.status_code == 200
        data = response.json()
        item = next(row for row in data["items"] if row["id"] == transfer_order.id)
        assert item["receipt_uploaded"] is False
        assert item["receipt_content_type"] is None
        assert item["receipt_uploaded_at"] is None
        assert item["receipt_viewed_at"] is None

    async def test_detail_with_receipt_returns_fields(
        self, client, db_session, transfer_order
    ):
        await _seed_receipt(db_session, transfer_order.id)
        response = await client.get(f"/api/v1/orders/{transfer_order.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["receipt_uploaded"] is True
        assert data["receipt_content_type"] == "image/jpeg"
        assert data["receipt_uploaded_at"] is not None
        assert data["receipt_viewed_at"] is not None

    async def test_detail_includes_paid_and_payment_method(
        self, client, transfer_order
    ):
        # S7 (O5): el panel necesita paid y payment_method en el detalle.
        response = await client.get(f"/api/v1/orders/{transfer_order.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["paid"] is False
        assert data["payment_method"] == "transfer"


class TestReceiptPersistence:

    async def test_fields_round_trip_through_repository(
        self, db_session, transfer_order
    ):
        now = await _seed_receipt(db_session, transfer_order.id, viewed=False)
        stored = await SQLOrderRepository(db_session).get(transfer_order.id)
        assert stored is not None
        assert stored.receipt_file == f"{transfer_order.id}.jpg"
        assert stored.receipt_content_type == "image/jpeg"
        assert stored.receipt_size_bytes == 2048
        assert stored.receipt_uploaded_at == now
        assert stored.receipt_viewed_at is None
        assert stored.receipt_deleted_at is None

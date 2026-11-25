import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import get_current_user, require_admin
from api.v1.invoicing.dependencies import get_invoice_repository
from api.v1.orders import receipt_service
from data.db import get_db as get_db_orig
from data.models import (
    IngredientORM,
    OrderItemORM,
    OrderORM,
    PaymentEventORM,
    StockMovementORM,
)
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from domain.order import Order, OrderItem, PaymentMethod
from domain.orders import OrderItemSnapshot, OrderItemSnapshotLine
from main import app

CUSTOMER = User(email="cliente@example.com", role=UserRole.CUSTOMER)
ADMIN = User(email="admin@example.com", role=UserRole.ADMIN)
OTHER = User(email="otro@example.com", role=UserRole.CUSTOMER)

PDF_BYTES = b"%PDF-1.7 fake receipt content"
JPEG_BYTES = b"\xff\xd8\xff\xe0fake jpeg"

INGREDIENT_ID = "ing1"
STOCK_INITIAL = Decimal("100")


@pytest_asyncio.fixture
async def client(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(receipt_service, "_RECEIPTS_DIR", tmp_path)

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
    await SQLUserRepository(db_session).save(CUSTOMER)
    await SQLUserRepository(db_session).save(OTHER)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


def _with_user(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override


async def _restore_customer():
    async def _override():
        return CUSTOMER

    app.dependency_overrides[get_current_user] = _override


def _snapshot() -> OrderItemSnapshot:
    return OrderItemSnapshot(
        lines=(
            OrderItemSnapshotLine(
                ingredient_id=INGREDIENT_ID,
                ingredient_name="Harina 000",
                qty=Decimal("2"),
                unit="kg",
                cost=Decimal("10"),
                is_missing=False,
            ),
        ),
        materials=Decimal("20"),
        waste=Decimal("1"),
        materials_con_merma=Decimal("21"),
        labor=Decimal("5"),
        gas=Decimal("2"),
        base=Decimal("28"),
        margin_pct=Decimal("50"),
        final=Decimal("42"),
        rounded=Decimal("42"),
    )


async def _seed_ingredient(db_session) -> None:
    db_session.add(
        IngredientORM(
            id=INGREDIENT_ID,
            name="Harina 000",
            unit="kg",
            price_per_unit="10",
            stock_qty=str(STOCK_INITIAL),
            low_stock_threshold="5",
            created_at=datetime.datetime.now(datetime.UTC),
        )
    )
    await db_session.commit()


async def _stock_qty(db_session) -> Decimal:
    row = await db_session.get(IngredientORM, INGREDIENT_ID)
    return Decimal(row.stock_qty)


async def _make_order(
    db_session,
    *,
    customer_id: str = CUSTOMER.id,
    payment_method: PaymentMethod = PaymentMethod.TRANSFER,
    with_snapshot: bool = True,
) -> Order:
    item = OrderItem(
        product_id="p1",
        product_name="Torta",
        quantity=1,
        unit_price=Decimal("1000"),
        portions=1,
    )
    order = Order(
        customer_id=customer_id,
        customer_name=CUSTOMER.email,
        customer_phone="11555555555",
        date=datetime.datetime.now(datetime.UTC),
        items=[item],
        payment_method=payment_method,
    )
    if with_snapshot:
        order.snapshots[item.id] = _snapshot()
    await SQLOrderRepository(db_session).add(order)
    return order


async def _set_status(db_session, order_id: str, status: str) -> None:
    orm = await db_session.get(OrderORM, order_id)
    orm.status = status
    await db_session.commit()


async def _seed_receipt(
    db_session, order_id: str, *, ext: str = "pdf", bytes_: bytes = PDF_BYTES
) -> None:
    receipt_service.write_receipt(order_id, bytes_, ext)
    now = datetime.datetime.now(datetime.UTC)
    orm = await db_session.get(OrderORM, order_id)
    orm.receipt_file = ext
    orm.receipt_content_type = "application/pdf" if ext == "pdf" else "image/jpeg"
    orm.receipt_size_bytes = len(bytes_)
    orm.receipt_uploaded_at = now
    await db_session.commit()


async def _payment_events(db_session, order_id: str) -> list[str]:
    rows = await db_session.execute(
        select(PaymentEventORM.status).where(
            PaymentEventORM.order_id == order_id
        )
    )
    return [row[0] for row in rows]


class TestUploadReceipt:

    async def test_upload_valid_pdf_returns_201_and_persists(
        self, client, db_session, tmp_path
    ):
        order = await _make_order(db_session)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("comprobante.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["receipt_uploaded"] is True
        assert data["receipt_content_type"] == "application/pdf"
        assert data["receipt_uploaded_at"] is not None
        # pending es implicito en transfer: None o "pending", nunca approved
        assert data["payment_status"] in (None, "pending")
        assert data["paid"] is False
        assert (tmp_path / f"{order.id}.pdf").read_bytes() == PDF_BYTES

    async def test_upload_existing_receipt_returns_409(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("otro.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "receipt_already_uploaded"

    async def test_upload_cash_order_returns_409(self, client, db_session):
        order = await _make_order(
            db_session, payment_method=PaymentMethod.CASH
        )
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("comprobante.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"] == "receipt_method_not_transfer"
        )

    async def test_upload_gif_disguised_as_jpeg_returns_422(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("foto.jpg", b"GIF89a fake", "image/jpeg")},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_invalid_type"

    async def test_upload_file_over_5mb_returns_422(self, client, db_session):
        order = await _make_order(db_session)
        big = b"%PDF-1.7 " + b"x" * (5 * 1024 * 1024 + 1)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("grande.pdf", big, "application/pdf")},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "receipt_too_large"

    async def test_upload_terminal_order_returns_409(self, client, db_session):
        order = await _make_order(db_session)
        await _set_status(db_session, order.id, "cancelled")
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("comprobante.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "receipt_order_terminal"

    async def test_upload_other_customers_order_returns_404(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(OTHER)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("comprobante.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 404
        await _restore_customer()

    async def test_admin_can_upload_for_customer(self, client, db_session):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt",
            files={"file": ("comprobante.pdf", PDF_BYTES, "application/pdf")},
        )
        assert response.status_code == 201
        assert response.json()["receipt_uploaded"] is True
        await _restore_customer()


class TestConfirmReceipt:

    async def test_confirm_from_new_pays_prepares_and_deducts_once(
        self, client, db_session
    ):
        await _seed_ingredient(db_session)
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)

        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt/confirm"
        )
        await _restore_customer()
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preparing"
        assert data["receipt_uploaded"] is True

        stored = await db_session.get(OrderORM, order.id)
        assert stored.payment_status == "approved"
        assert stored.paid_at is not None
        assert await _stock_qty(db_session) == STOCK_INITIAL - Decimal("2")

        rows = await db_session.execute(
            select(StockMovementORM).where(
                StockMovementORM.ingredient_id == INGREDIENT_ID,
                StockMovementORM.ref == order.id,
            )
        )
        movements = rows.scalars().all()
        assert len(movements) == 1

    async def test_confirm_cancelled_order_returns_409(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        await _set_status(db_session, order.id, "cancelled")
        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt/confirm"
        )
        await _restore_customer()
        assert response.status_code == 409
        assert (
            response.json()["detail"] == "receipt_order_not_receivable"
        )

    async def test_confirm_without_receipt_returns_404(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt/confirm"
        )
        await _restore_customer()
        assert response.status_code == 404
        assert response.json()["detail"] == "receipt_not_found"


class TestRejectReceipt:

    async def test_reject_from_new_cancels_and_rejects_payment(
        self, client, db_session
    ):
        await _seed_ingredient(db_session)
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)

        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt/reject"
        )
        await _restore_customer()
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        stored = await db_session.get(OrderORM, order.id)
        assert stored.payment_status == "rejected"
        assert await _stock_qty(db_session) == STOCK_INITIAL

    async def test_reject_without_receipt_returns_404(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.post(
            f"/api/v1/orders/{order.id}/receipt/reject"
        )
        await _restore_customer()
        assert response.status_code == 404
        assert response.json()["detail"] == "receipt_not_found"


class TestDeleteReceipt:

    async def test_delete_delivered_order_returns_204_and_clears(
        self, client, db_session, tmp_path
    ):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        await _set_status(db_session, order.id, "delivered")

        _with_user(ADMIN)
        response = await client.delete(f"/api/v1/orders/{order.id}/receipt")
        await _restore_customer()
        assert response.status_code == 204
        assert not (tmp_path / f"{order.id}.pdf").exists()

        stored = await db_session.get(OrderORM, order.id)
        assert stored.receipt_file is None
        assert stored.receipt_content_type is None
        assert stored.receipt_size_bytes is None
        assert stored.receipt_uploaded_at is None
        assert stored.receipt_deleted_at is not None
        assert stored.payment_method == "transfer"
        assert "deleted" in await _payment_events(db_session, order.id)

    async def test_delete_non_delivered_order_returns_409(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        await _set_status(db_session, order.id, "preparing")
        _with_user(ADMIN)
        response = await client.delete(f"/api/v1/orders/{order.id}/receipt")
        await _restore_customer()
        assert response.status_code == 409
        assert (
            response.json()["detail"] == "receipt_not_deletable"
        )

    async def test_delete_without_receipt_returns_404(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.delete(f"/api/v1/orders/{order.id}/receipt")
        await _restore_customer()
        assert response.status_code == 404
        assert response.json()["detail"] == "receipt_not_found"


class TestDownloadReceipt:

    async def test_download_without_receipt_returns_404(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.get(f"/api/v1/orders/{order.id}/receipt")
        await _restore_customer()
        assert response.status_code == 404
        assert response.json()["detail"] == "receipt_not_found"

    async def test_owner_download_returns_binary_without_touching_viewed_at(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        response = await client.get(f"/api/v1/orders/{order.id}/receipt")
        assert response.status_code == 200
        assert response.content == PDF_BYTES
        assert response.headers["content-type"].startswith("application/pdf")

        stored = await db_session.get(OrderORM, order.id)
        assert stored.receipt_viewed_at is None

    async def test_admin_download_sets_viewed_at(self, client, db_session):
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        _with_user(ADMIN)
        response = await client.get(f"/api/v1/orders/{order.id}/receipt")
        await _restore_customer()
        assert response.status_code == 200
        assert response.content == PDF_BYTES

        stored = await db_session.get(OrderORM, order.id)
        assert stored.receipt_viewed_at is not None


class TestMarkPaidGate:

    async def test_transfer_without_receipt_returns_409_receipt_required(
        self, client, db_session
    ):
        order = await _make_order(db_session)
        _with_user(ADMIN)
        response = await client.patch(f"/api/v1/orders/{order.id}/paid")
        await _restore_customer()
        assert response.status_code == 409
        assert response.json()["detail"] == "receipt_required"

    async def test_transfer_with_receipt_delegates_to_confirm(
        self, client, db_session
    ):
        await _seed_ingredient(db_session)
        order = await _make_order(db_session)
        await _seed_receipt(db_session, order.id)
        _with_user(ADMIN)
        response = await client.patch(f"/api/v1/orders/{order.id}/paid")
        await _restore_customer()
        assert response.status_code == 200
        assert response.json()["paid"] is True

        stored = await db_session.get(OrderORM, order.id)
        assert stored.payment_status == "approved"
        assert stored.status == "preparing"
        assert await _stock_qty(db_session) == STOCK_INITIAL - Decimal("2")

    async def test_cash_order_mark_paid_still_works(
        self, client, db_session
    ):
        order = await _make_order(
            db_session, payment_method=PaymentMethod.CASH, with_snapshot=False
        )
        _with_user(ADMIN)
        response = await client.patch(f"/api/v1/orders/{order.id}/paid")
        await _restore_customer()
        assert response.status_code == 200
        assert response.json()["paid"] is True
        stored = await db_session.get(OrderORM, order.id)
        assert stored.payment_status == "approved"

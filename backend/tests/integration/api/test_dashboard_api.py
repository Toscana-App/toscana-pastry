import datetime
import json
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from data.db import get_db
from data.models import OrderItemORM, OrderORM
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app

PERIOD = {"date_from": "2026-05-01", "date_to": "2026-05-31"}
BASE = "/api/v1/dashboard"


def _utc(*args: int) -> datetime.datetime:
    return datetime.datetime(*args, tzinfo=datetime.UTC)


async def _add_order(
    session,
    *,
    when: datetime.datetime,
    status: str,
    payment_method: str,
    items: list[tuple[str, str, int, str | None] | tuple[str, str, int, str | None, str | None]],
    paid: bool = False,
    discount: str | None = None,
) -> None:
    order_id = str(uuid.uuid4())
    session.add(
        OrderORM(
            id=order_id,
            customer_id="customer-1",
            code=f"TP{uuid.uuid4().hex[:6].upper()}",
            status=status,
            date=when,
            payment_method=payment_method,
            discount_amount=discount,
            paid_at=when if paid else None,
            created_at=when,
        )
    )
    await session.flush()
    for index, item in enumerate(items):
        product_id, name, quantity, unit_price = item[:4]
        snapshot = item[4] if len(item) > 4 else None
        session.add(
            OrderItemORM(
                id=str(uuid.uuid4()),
                order_id=order_id,
                product_id=product_id,
                product_name=name,
                quantity=quantity,
                unit_price=unit_price,
                snapshot=snapshot,
                position=index,
            )
        )
    await session.flush()


@pytest_asyncio.fixture
async def seeded(db_session):
    await _add_order(
        db_session,
        when=_utc(2026, 5, 2, 10),
        status="nuevo",
        payment_method="cash",
        items=[("torta", "Torta", 2, "1000.00"), ("alfajor", "Alfajor", 10, "200.00")],
        discount="500",
    )
    await _add_order(
        db_session,
        when=_utc(2026, 5, 2, 15),
        status="confirmado",
        payment_method="mercadopago",
        items=[("torta", "Torta", 1, "1000.00")],
        paid=True,
    )
    await _add_order(
        db_session,
        when=_utc(2026, 5, 4, 9),
        status="entregado",
        payment_method="cash",
        items=[("alfajor", "Alfajor", 5, "200.00")],
        paid=True,
        discount="",
    )
    await _add_order(
        db_session,
        when=_utc(2026, 5, 5, 9),
        status="cancelado",
        payment_method="cash",
        items=[("torta", "Torta", 3, "1000.00")],
    )
    await _add_order(
        db_session,
        when=_utc(2026, 4, 30, 23, 59),
        status="nuevo",
        payment_method="cash",
        items=[("torta", "Torta", 100, "1000.00")],
    )
    await _add_order(
        db_session,
        when=_utc(2026, 6, 1, 0, 0),
        status="nuevo",
        payment_method="cash",
        items=[("torta", "Torta", 100, "1000.00")],
    )
    await db_session.commit()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    users = SQLUserRepository(db_session)
    await users.save(User(email="admin@example.com", role=UserRole.ADMIN))
    await users.save(User(email="customer@example.com", role=UserRole.CUSTOMER))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


async def _headers(client: AsyncClient, email: str) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.cookies['auth_token']}"}


@pytest_asyncio.fixture
async def admin(client) -> dict:
    return await _headers(client, "admin@example.com")


class TestSummary:
    async def test_totals_exclude_cancelled_and_out_of_period(
        self, client, admin, seeded
    ):
        response = await client.get(f"{BASE}/summary", params=PERIOD, headers=admin)
        assert response.status_code == 200
        body = response.json()
        assert body["date_from"] == "2026-05-01"
        assert body["date_to"] == "2026-05-31"
        assert body["revenue"] == 550000
        assert body["orders_count"] == 3
        assert body["average_ticket"] == 183333
        assert body["paid_revenue"] == 200000
        assert body["pending_revenue"] == 350000
        assert body["cancelled_count"] == 1

    async def test_period_end_is_inclusive_and_next_day_excluded(
        self, client, admin, seeded
    ):
        response = await client.get(
            f"{BASE}/summary",
            params={"date_from": "2026-05-02", "date_to": "2026-05-02"},
            headers=admin,
        )
        body = response.json()
        assert body["orders_count"] == 2
        assert body["revenue"] == 450000

    async def test_empty_database_returns_zeros(self, client, admin):
        response = await client.get(f"{BASE}/summary", params=PERIOD, headers=admin)
        assert response.status_code == 200
        body = response.json()
        assert body["revenue"] == 0
        assert body["orders_count"] == 0
        assert body["average_ticket"] == 0
        assert body["cancelled_count"] == 0

    async def test_defaults_to_last_thirty_days(self, client, admin):
        response = await client.get(f"{BASE}/summary", headers=admin)
        assert response.status_code == 200
        body = response.json()
        start = datetime.date.fromisoformat(body["date_from"])
        end = datetime.date.fromisoformat(body["date_to"])
        assert (end - start).days + 1 == 30

    async def test_cache_control_header(self, client, admin):
        response = await client.get(f"{BASE}/summary", params=PERIOD, headers=admin)
        assert response.headers["cache-control"] == "private, max-age=30"


class TestSalesSeries:
    async def test_daily_series_is_zero_filled_for_whole_period(
        self, client, admin, seeded
    ):
        response = await client.get(
            f"{BASE}/sales-series", params=PERIOD, headers=admin
        )
        assert response.status_code == 200
        body = response.json()
        assert body["granularity"] == "day"
        points = body["points"]
        assert len(points) == 31
        by_day = {p["bucket"]: p for p in points}
        assert by_day["2026-05-02"] == {
            "bucket": "2026-05-02",
            "revenue": 450000,
            "orders_count": 2,
        }
        assert by_day["2026-05-04"]["revenue"] == 100000
        assert by_day["2026-05-05"] == {
            "bucket": "2026-05-05",
            "revenue": 0,
            "orders_count": 0,
        }
        assert by_day["2026-05-01"]["orders_count"] == 0

    async def test_weekly_series_buckets_start_on_monday(
        self, client, admin, seeded
    ):
        response = await client.get(
            f"{BASE}/sales-series",
            params={**PERIOD, "granularity": "week"},
            headers=admin,
        )
        points = response.json()["points"]
        assert [p["bucket"] for p in points] == [
            "2026-04-27",
            "2026-05-04",
            "2026-05-11",
            "2026-05-18",
            "2026-05-25",
        ]
        assert points[0]["revenue"] == 450000
        assert points[0]["orders_count"] == 2
        assert points[1]["revenue"] == 100000
        assert points[2]["orders_count"] == 0

    async def test_monthly_series_single_bucket(self, client, admin, seeded):
        response = await client.get(
            f"{BASE}/sales-series",
            params={**PERIOD, "granularity": "month"},
            headers=admin,
        )
        assert response.json()["points"] == [
            {"bucket": "2026-05-01", "revenue": 550000, "orders_count": 3}
        ]

    async def test_invalid_granularity_is_422(self, client, admin):
        response = await client.get(
            f"{BASE}/sales-series",
            params={**PERIOD, "granularity": "year"},
            headers=admin,
        )
        assert response.status_code == 422


class TestOrdersByStatus:
    async def test_counts_every_status_in_period(self, client, admin, seeded):
        response = await client.get(
            f"{BASE}/orders-by-status", params=PERIOD, headers=admin
        )
        assert response.status_code == 200
        assert response.json()["items"] == [
            {"status": "nuevo", "orders_count": 1},
            {"status": "confirmado", "orders_count": 1},
            {"status": "entregado", "orders_count": 1},
            {"status": "cancelado", "orders_count": 1},
        ]

    async def test_empty_period_lists_all_statuses_with_zero(self, client, admin):
        response = await client.get(
            f"{BASE}/orders-by-status", params=PERIOD, headers=admin
        )
        items = response.json()["items"]
        assert [i["status"] for i in items] == [
            "nuevo",
            "confirmado",
            "entregado",
            "cancelado",
        ]
        assert all(i["orders_count"] == 0 for i in items)


class TestTopProducts:
    async def test_orders_by_revenue_then_quantity_excluding_cancelled(
        self, client, admin, seeded
    ):
        response = await client.get(
            f"{BASE}/top-products", params=PERIOD, headers=admin
        )
        assert response.status_code == 200
        assert response.json()["items"] == [
            {
                "product_id": "alfajor",
                "product_name": "Alfajor",
                "quantity": 15,
                "revenue": 300000,
            },
            {
                "product_id": "torta",
                "product_name": "Torta",
                "quantity": 3,
                "revenue": 300000,
            },
        ]

    async def test_limit_truncates_results(self, client, admin, seeded):
        response = await client.get(
            f"{BASE}/top-products",
            params={**PERIOD, "limit": 1},
            headers=admin,
        )
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["product_id"] == "alfajor"

    async def test_limit_out_of_range_is_422(self, client, admin):
        for limit in (0, 21):
            response = await client.get(
                f"{BASE}/top-products",
                params={**PERIOD, "limit": limit},
                headers=admin,
            )
            assert response.status_code == 422, limit


class TestPaymentMethods:
    async def test_split_by_method_excluding_cancelled(self, client, admin, seeded):
        response = await client.get(
            f"{BASE}/payment-methods", params=PERIOD, headers=admin
        )
        assert response.status_code == 200
        assert response.json()["items"] == [
            {"payment_method": "cash", "orders_count": 2, "revenue": 450000},
            {"payment_method": "mercadopago", "orders_count": 1, "revenue": 100000},
        ]

    async def test_empty_period_returns_empty_list(self, client, admin):
        response = await client.get(
            f"{BASE}/payment-methods", params=PERIOD, headers=admin
        )
        assert response.json()["items"] == []


class TestInvalidPeriod:
    async def test_from_after_to_is_problem_json_422(self, client, admin):
        response = await client.get(
            f"{BASE}/summary",
            params={"date_from": "2026-05-31", "date_to": "2026-05-01"},
            headers=admin,
        )
        assert response.status_code == 422
        assert response.headers["content-type"].startswith(
            "application/problem+json"
        )
        body = response.json()
        assert body["status"] == 422
        assert body["code"] == "date_from_after_date_to"

    async def test_span_too_long_is_problem_json_422(self, client, admin):
        response = await client.get(
            f"{BASE}/sales-series",
            params={"date_from": "2024-01-01", "date_to": "2026-01-01"},
            headers=admin,
        )
        assert response.status_code == 422
        assert response.json()["code"] == "period_too_long"

    async def test_malformed_date_is_422(self, client, admin):
        response = await client.get(
            f"{BASE}/summary", params={"date_from": "not-a-date"}, headers=admin
        )
        assert response.status_code == 422

    async def test_every_endpoint_rejects_invalid_period(self, client, admin):
        params = {"date_from": "2026-05-31", "date_to": "2026-05-01"}
        for path in (
            "summary",
            "sales-series",
            "orders-by-status",
            "top-products",
            "payment-methods",
        ):
            response = await client.get(f"{BASE}/{path}", params=params, headers=admin)
            assert response.status_code == 422, path


class TestAuthorization:
    PATHS = (
        "summary",
        "sales-series",
        "orders-by-status",
        "top-products",
        "payment-methods",
    )

    async def test_anonymous_gets_401(self, client):
        for path in self.PATHS:
            response = await client.get(f"{BASE}/{path}", params=PERIOD)
            assert response.status_code == 401, path

    async def test_customer_gets_403(self, client):
        headers = await _headers(client, "customer@example.com")
        for path in self.PATHS:
            response = await client.get(f"{BASE}/{path}", params=PERIOD, headers=headers)
            assert response.status_code == 403, path


def _snapshot(rounded: str) -> str:
    return json.dumps({"lines": [], "final": rounded, "rounded": rounded})


@pytest_asyncio.fixture
async def admin_created(db_session):
    await _add_order(
        db_session,
        when=_utc(2026, 5, 10, 12),
        status="nuevo",
        payment_method="transfer",
        items=[
            ("torta", "Torta", 2, None, _snapshot("2500.00")),
            ("alfajor", "Alfajor", 3, None, _snapshot("900.50")),
        ],
    )
    await _add_order(
        db_session,
        when=_utc(2026, 5, 10, 18),
        status="confirmado",
        payment_method="transfer",
        items=[
            ("torta", "Torta", 1, None, None),
            ("alfajor", "Alfajor", 1, None, "{}"),
            ("torta", "Torta", 1, None, "not json"),
        ],
    )
    await db_session.commit()


class TestAdminCreatedOrdersWithoutUnitPrice:
    async def test_summary_uses_snapshot_rounded(self, client, admin, admin_created):
        response = await client.get(f"{BASE}/summary", params=PERIOD, headers=admin)
        assert response.status_code == 200
        body = response.json()
        assert body["revenue"] == 340050
        assert body["orders_count"] == 2

    async def test_series_uses_snapshot_rounded(self, client, admin, admin_created):
        response = await client.get(
            f"{BASE}/sales-series", params=PERIOD, headers=admin
        )
        by_day = {p["bucket"]: p for p in response.json()["points"]}
        assert by_day["2026-05-10"] == {
            "bucket": "2026-05-10",
            "revenue": 340050,
            "orders_count": 2,
        }

    async def test_top_products_use_snapshot_rounded(
        self, client, admin, admin_created
    ):
        response = await client.get(
            f"{BASE}/top-products", params=PERIOD, headers=admin
        )
        assert response.status_code == 200
        assert response.json()["items"] == [
            {
                "product_id": "torta",
                "product_name": "Torta",
                "quantity": 4,
                "revenue": 250000,
            },
            {
                "product_id": "alfajor",
                "product_name": "Alfajor",
                "quantity": 4,
                "revenue": 90050,
            },
        ]

    async def test_payment_split_uses_snapshot_rounded(
        self, client, admin, admin_created
    ):
        response = await client.get(
            f"{BASE}/payment-methods", params=PERIOD, headers=admin
        )
        assert response.json()["items"] == [
            {"payment_method": "transfer", "orders_count": 2, "revenue": 340050},
        ]

    async def test_missing_or_malformed_snapshot_counts_as_zero(
        self, client, admin, db_session
    ):
        await _add_order(
            db_session,
            when=_utc(2026, 5, 11, 12),
            status="nuevo",
            payment_method="cash",
            items=[
                ("torta", "Torta", 1, None, None),
                ("torta", "Torta", 1, "", "{bad json"),
            ],
        )
        await db_session.commit()
        for path in ("summary", "sales-series", "top-products", "payment-methods"):
            response = await client.get(f"{BASE}/{path}", params=PERIOD, headers=admin)
            assert response.status_code == 200, path
        summary = (
            await client.get(f"{BASE}/summary", params=PERIOD, headers=admin)
        ).json()
        assert summary["revenue"] == 0
        assert summary["orders_count"] == 1

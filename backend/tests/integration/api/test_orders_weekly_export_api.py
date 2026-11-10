import datetime
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from data.models import BudgetItemORM, BudgetORM, CustomerORM, OrderItemORM, OrderORM
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.orders.router import get_order_repository
from domain.models import User, UserRole

ORDER_SNAPSHOT = {
    "lines": [],
    "materials": "0",
    "waste": "0",
    "materials_con_merma": "0",
    "labor": "0",
    "gas": "0",
    "base": "0",
    "margin_pct": "0",
    "final": "0",
    "rounded": "0",
}


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _customer_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "customer@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _seed_customer(session: AsyncSession, cid: str, name: str, phone: str):
    now = datetime.datetime.now(datetime.UTC)
    session.add(
        CustomerORM(
            id=cid,
            name=name,
            phone=phone,
            name_norm=name.lower().replace(" ", "_"),
            phone_norm=phone,
            created_at=now,
        )
    )
    await session.commit()


async def _seed_order(
    session: AsyncSession,
    oid: str,
    customer: str,
    name: str,
    phone: str,
    order_date: datetime.date,
    status: str,
    total_cents: int,
    paid: bool = False,
    method: str = "cash",
):
    now = datetime.datetime.now(datetime.UTC)
    await _seed_customer(session, customer, name, phone)
    session.add(
        OrderORM(
            id=oid,
            code=f"T-0001-{oid[-4:]}",
            customer_id=customer,
            customer_name=name,
            customer_phone=phone,
            date=datetime.datetime(
                order_date.year, order_date.month, order_date.day, 12
            ),
            status=status,
            paid_at=now if paid else None,
            payment_method=method,
            created_at=now,
            updated_at=now,
        )
    )
    snap = dict(ORDER_SNAPSHOT)
    snap["final"] = f"{total_cents / 100:.2f}"
    snap["rounded"] = f"{total_cents / 100:.2f}"
    session.add(
        OrderItemORM(
            id=f"{oid}-i1",
            order_id=oid,
            product_id="p1",
            product_name="Tortín de vainilla",
            quantity=1,
            portions=1,
            note="",
            position=0,
            snapshot=json.dumps(snap),
        )
    )
    await session.commit()


async def _seed_budget(
    session: AsyncSession,
    bid: str,
    seq: str,
    customer: str,
    name: str,
    phone: str,
    created: datetime.date,
    status: str,
    unit_selling_cents: int,
    qty: int = 1,
):
    now = datetime.datetime.now(datetime.UTC)
    await _seed_customer(session, customer, name, phone)
    session.add(
        BudgetORM(
            id=bid,
            seq=seq,
            customer_id=customer,
            customer_name=name,
            customer_phone=phone,
            status=status,
            calculation_mode="cost_plus",
            version=0,
            created_at=datetime.datetime(
                created.year, created.month, created.day, 10
            ),
            updated_at=datetime.datetime(
                created.year, created.month, created.day, 10
            ),
        )
    )
    session.add(
        BudgetItemORM(
            id=f"{bid}-i1",
            budget_id=bid,
            product_id="p1",
            product_name="Torta red velvet",
            qty=qty,
            unit_cost="50.00",
            unit_selling=f"{unit_selling_cents / 100:.2f}",
            price_overridden=False,
            position=0,
        )
    )
    await session.commit()


def _this_week():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday, monday + datetime.timedelta(days=6)




@pytest.mark.asyncio
async def test_weekly_requires_authentication(client, db_session):
    response = await client.get("/api/v1/orders/weekly")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_weekly_forbidden_for_customer(client, db_session):
    token = await _customer_token(client)
    response = await client.get(
        "/api/v1/orders/weekly", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_weekly_default_week_aggregates(client, db_session):
    monday, _ = _this_week()
    await _seed_order(db_session, "ord-1", "c1", "Juan Pérez", "+54 9 11 5555-0001",
                      monday, "confirmado", 1234567, paid=True, method="cash")
    await _seed_order(db_session, "ord-2", "c2", "María Gómez", "+54 9 11 5555-0002",
                      monday + datetime.timedelta(days=1), "entregado", 80000,
                      paid=False, method="mp")
    await _seed_order(db_session, "ord-3", "c3", "Fuera de Semana",
                      "+54 9 11 5555-0003", monday - datetime.timedelta(days=8),
                      "confirmado", 500000)
    await _seed_order(db_session, "ord-4", "c4", "Pendiente Confirmar",
                      "+54 9 11 5555-0004", monday, "nuevo", 70000)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/orders/weekly", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["week"]["from"] == monday.isoformat()
    assert body["week"]["to"] == (monday + datetime.timedelta(days=6)).isoformat()
    assert body["totals"]["amount"] == 1234567 + 80000
    assert body["totals"]["paid"] == 1234567
    assert body["totals"]["unpaid"] == 80000
    items = body["items"]
    assert len(items) == 2
    names = {i["customer"] for i in items}
    assert names == {"Juan Pérez", "María Gómez"}
    juan = next(i for i in items if i["customer"] == "Juan Pérez")
    assert juan["total"] == 1234567
    assert juan["paid"] is True
    assert juan["payment_method"] == "cash"


@pytest.mark.asyncio
async def test_weekly_iso_week_param(client, db_session):
    anchor = datetime.date(2026, 11, 2)
    iso = f"{anchor.isocalendar().year}-W{anchor.isocalendar().week:02d}"
    await _seed_order(db_session, "ord-1", "c1", "Juan Pérez", "+54 9 11 5555-0001",
                      anchor, "confirmado", 100000, paid=True)

    token = await _admin_token(client)
    response = await client.get(
        f"/api/v1/orders/weekly?week={iso}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["week"]["from"] == anchor.isoformat()
    assert body["week"]["to"] == (anchor + datetime.timedelta(days=6)).isoformat()
    assert body["totals"]["amount"] == 100000


@pytest.mark.asyncio
async def test_weekly_bad_week_422(client, db_session):
    token = await _admin_token(client)
    for bad in ("2026-W99", "no-es-una-semana", "2026/44"):
        response = await client.get(
            f"/api/v1/orders/weekly?week={bad}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, bad




@pytest.mark.asyncio
async def test_orders_export_csv_default(client, db_session):
    monday, _ = _this_week()
    await _seed_order(db_session, "ord-1", "c1", "Juan Pérez", "+54 9 11 5555-0001",
                      monday, "confirmado", 1234567, paid=True)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/orders/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert "id,cliente,fecha,items,total,estado,pago,metodo" in body
    assert "Juan Pérez" in body
    assert "confirmado" in body
    assert "$12.345,67" in body


@pytest.mark.asyncio
async def test_orders_export_filters(client, db_session):
    monday, _ = _this_week()
    await _seed_order(db_session, "ord-1", "c1", "Con Filtro", "+54 9 11 5555-0011",
                      monday, "confirmado", 100000, paid=True)
    await _seed_order(db_session, "ord-2", "c2", "Sin Filtro", "+54 9 11 5555-0012",
                      monday, "nuevo", 200000, paid=False)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/orders/export?status=confirmado",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.text
    assert "Con Filtro" in body
    assert "Sin Filtro" not in body

    response = await client.get(
        "/api/v1/orders/export?paid=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.text
    assert "Sin Filtro" in body
    assert "Con Filtro" not in body


@pytest.mark.asyncio
async def test_orders_export_pdf(client, db_session):
    monday, _ = _this_week()
    await _seed_order(db_session, "ord-1", "c1", "Juan Pérez", "+54 9 11 5555-0001",
                      monday, "confirmado", 1234567, paid=True)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/orders/export?format=pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert "pedidos_" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_orders_export_invalid_format_422(client, db_session):
    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/orders/export?format=xlsx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_orders_export_requires_authentication(client, db_session):
    assert (await client.get("/api/v1/orders/export")).status_code == 401




@pytest.mark.asyncio
async def test_budgets_export_csv_default(client, db_session):
    created = datetime.date(2026, 11, 1)
    await _seed_budget(db_session, "bud-1", "00042", "c1", "María Gómez",
                       "+54 9 11 5555-0100", created, "enviado", 452000)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/budgets/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    body = response.text
    assert "seq,cliente,telefono,fecha,enviado,estado,total_venta,iva" in body
    assert "#00042" in body
    assert "María Gómez" in body
    assert "enviado" in body
    assert "$4.520,00" in body
    assert "$949,20" in body


@pytest.mark.asyncio
async def test_budgets_export_pdf(client, db_session):
    created = datetime.date(2026, 11, 1)
    await _seed_budget(db_session, "bud-1", "00042", "c1", "María Gómez",
                       "+54 9 11 5555-0100", created, "enviado", 452000)

    token = await _admin_token(client)
    response = await client.get(
        "/api/v1/budgets/export?format=pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert "presupuestos_" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_budgets_export_requires_authentication(client, db_session):
    assert (await client.get("/api/v1/budgets/export")).status_code == 401

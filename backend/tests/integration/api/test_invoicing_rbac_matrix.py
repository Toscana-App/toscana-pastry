"""T4 — Matriz RBAC del módulo de facturación (RNF-P13-01).

Anónimo → 401; token ``customer``/``negocio`` → 403; ``admin`` → 2xx.
Es el test de regresión permanente: nadie fuera del rol admin emite ni lee
comprobantes, settings fiscales o CAEs.
"""

import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.v1.auth.dependencies import get_user_repository
from api.v1.invoicing.dependencies import (
    get_afip_client,
    get_invoice_repository,
    get_invoicing_order_repository,
)
from api.v1.orders.dependencies import get_order_repository
from data.db import get_db
from data.models import Base, OrderItemORM, OrderORM
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.invoicing import AfipCaeResult
from domain.models import User, UserRole
from main import app

CAE = "75123456789012"

SETTINGS = {
    "cuit": "30123456789",
    "punto_venta": 1,
    "razon_social": "PASTELERIA TOSCANA",
    "domicilio": "Av. Corrientes 123",
    "condicion_iva": "Responsable Monotributo",
    "categoria_monotributo": "F",
    "ingresos_brutos": "Exento",
    "inicio_actividades": "01/05/2020",
}


class FakeAfipClient:
    def __init__(self) -> None:
        self.ultimo = 0

    async def last_authorized(
        self, *, cuit: str, punto_venta: int, tipo_cbte: int
    ) -> int:
        return self.ultimo

    async def request_cae(self, *, cuit: str, request: dict) -> AfipCaeResult:
        self.ultimo = request["FeDetReq"]["FECAEDetRequest"][0]["CbteDesde"]
        return AfipCaeResult(
            resultado="A", cae=CAE, cae_vto=datetime.date(2026, 11, 21)
        )


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_invoice_repository():
        yield SQLInvoiceRepository(db_session)

    async def override_get_invoicing_order_repository():
        yield SQLOrderRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_invoice_repository] = override_get_invoice_repository
    app.dependency_overrides[get_invoicing_order_repository] = (
        override_get_invoicing_order_repository
    )
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    afip_client = FakeAfipClient()
    app.dependency_overrides[get_afip_client] = lambda: afip_client

    user_repo = SQLUserRepository(db_session)
    await user_repo.save(User(email="admin@example.com", role=UserRole.ADMIN))
    await user_repo.save(User(email="negocio@example.com", role=UserRole.NEGOCIO))
    await user_repo.save(User(email="customer@example.com", role=UserRole.CUSTOMER))

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as async_client:
            yield async_client
    finally:
        app.dependency_overrides = {}


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.cookies["auth_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_order(db_session, suffix: str = "1") -> str:
    order_id = f"ord-matrix-{suffix}"
    db_session.add(
        OrderORM(
            id=order_id,
            customer_id="cust-1",
            code=f"TPMATRIX{suffix}",
            status="entregado",
            date=datetime.datetime(2026, 11, 11, 12, 0, tzinfo=datetime.UTC),
            payment_method="cash",
            delivery_mode="pickup",
            delivery_address="",
            customer_name="Maria",
        )
    )
    db_session.add(
        OrderItemORM(
            id=f"item-matrix-{suffix}",
            order_id=order_id,
            product_id="prod-1",
            product_name="Torta de limon",
            quantity=1,
            unit_price="5200.00",
            portion_note="",
            qty=1,
            portions=20,
            note="",
            position=1,
        )
    )
    await db_session.commit()
    return order_id


@pytest_asyncio.fixture
async def seeded(client: AsyncClient, db_session) -> dict:
    """Settings + un comprobante emitido (GET por id) y un pedido libre."""
    order_id = await _seed_order(db_session)
    free_order_id = await _seed_order(db_session, "2")
    token = await _token_for(client, "admin@example.com")
    headers = _auth(token)
    settings = await client.put(
        "/api/v1/invoicing/settings", json=SETTINGS, headers=headers
    )
    assert settings.status_code == 200, settings.text
    created = await client.post(
        "/api/v1/invoices",
        json={
            "order_id": order_id,
            "concepto": 1,
            "doc_tipo": 99,
            "doc_nro": 0,
            "receptor_nombre": "Juan Perez",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return {
        "order_id": order_id,
        "order_id_free": free_order_id,
        "invoice_id": created.json()["id"],
    }


ENDPOINTS = [
    ("POST", "/api/v1/invoices", "invoice"),
    ("GET", "/api/v1/invoices", None),
    ("GET", "/api/v1/invoices/{invoice_id}", None),
    ("GET", "/api/v1/invoicing/settings", None),
    ("PUT", "/api/v1/invoicing/settings", "settings"),
]


def _request_args(kind: str | None, seeded: dict) -> dict:
    if kind == "invoice":
        return {
            "json": {
                "order_id": seeded["order_id_free"],
                "concepto": 1,
                "doc_tipo": 99,
                "doc_nro": 0,
                "receptor_nombre": "Juan Perez",
            }
        }
    if kind == "settings":
        return {"json": SETTINGS}
    return {}


@pytest.mark.parametrize(("method", "path", "kind"), ENDPOINTS)
async def test_anonimo_401(method, path, kind, client: AsyncClient, seeded: dict):
    response = await client.request(method, path.format(**seeded), **_request_args(kind, seeded))
    assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize(("method", "path", "kind"), ENDPOINTS)
async def test_cliente_403(method, path, kind, client: AsyncClient, seeded: dict):
    token = await _token_for(client, "customer@example.com")
    response = await client.request(
        method,
        path.format(**seeded),
        headers=_auth(token),
        **_request_args(kind, seeded),
    )
    assert response.status_code == 403, f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize(("method", "path", "kind"), ENDPOINTS)
async def test_negocio_403(method, path, kind, client: AsyncClient, seeded: dict):
    token = await _token_for(client, "negocio@example.com")
    response = await client.request(
        method,
        path.format(**seeded),
        headers=_auth(token),
        **_request_args(kind, seeded),
    )
    assert response.status_code == 403, f"{method} {path} -> {response.status_code}"


@pytest.mark.parametrize(("method", "path", "kind"), ENDPOINTS)
async def test_admin_2xx(method, path, kind, client: AsyncClient, seeded: dict):
    token = await _token_for(client, "admin@example.com")
    response = await client.request(
        method,
        path.format(**seeded),
        headers=_auth(token),
        **_request_args(kind, seeded),
    )
    assert response.status_code in (200, 201), (
        f"{method} {path} -> {response.status_code}: {response.text[:200]}"
    )

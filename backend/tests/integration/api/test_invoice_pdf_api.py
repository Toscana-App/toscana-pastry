"""T6 — Descarga del PDF oficial de un comprobante (RF-P13-06).

Render por el borde ``InvoicePdfRenderer`` (fake en estos tests): cero red.
Corre igual en local (sqlite) y en CI (Postgres).
"""

import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.v1.auth.dependencies import get_user_repository
from api.v1.invoicing.dependencies import (
    get_afip_client,
    get_invoice_pdf_renderer,
    get_invoice_repository,
)
from data.db import get_db
from data.models import Base, OrderORM
from data.pdf.client import PdfServiceError
from data.repositories.sql_invoice_repository import SQLInvoiceRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.invoicing import (
    ESTADO_RECHAZADO,
    Invoice,
    InvoiceItem,
    InvoicingSettings,
)
from domain.models import User, UserRole
from main import app

CAE = "75123456789012"
FECHA = datetime.date(2026, 11, 11)
CAE_VTO = datetime.date(2026, 11, 21)

SETTINGS = InvoicingSettings(
    cuit="30123456789",
    punto_venta=1,
    razon_social="PASTELERIA TOSCANA",
    domicilio="Av. Corrientes 123",
    condicion_iva="Responsable Monotributo",
    categoria_monotributo="F",
    ingresos_brutos="Exento",
    inicio_actividades="01/05/2020",
)


def _invoice(order_id: str, **overrides) -> Invoice:
    base = {
        "order_id": order_id,
        "punto_venta": 1,
        "tipo_cbte": 11,
        "numero": 7,
        "cae": CAE,
        "cae_vto": CAE_VTO,
        "fecha": FECHA,
        "imp_total": "5200.00",
        "receptor_doc_tipo": 99,
        "receptor_doc_nro": 0,
        "receptor_nombre": "Maria",
    }
    base.update(overrides)
    return Invoice(**base)


class FakeInvoicePdfRenderer:
    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.error: Exception | None = None

    def render_invoice_arca(self, payload: dict) -> bytes:
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return b"%PDF-1.4\n%fake invoice\n%%EOF\n"


class FakeAfipClient:
    async def last_authorized(self, *, cuit, punto_venta, tipo_cbte) -> int:
        return 0

    async def request_cae(self, *, cuit, request):  # pragma: no cover - no se usa
        raise AssertionError("el PDF no debe emitir comprobantes")


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


@pytest.fixture
def fake_renderer() -> FakeInvoicePdfRenderer:
    return FakeInvoicePdfRenderer()


@pytest_asyncio.fixture
async def client(db_session, fake_renderer):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_invoice_repository():
        yield SQLInvoiceRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_invoice_repository] = override_get_invoice_repository
    app.dependency_overrides[get_afip_client] = lambda: FakeAfipClient()
    app.dependency_overrides[get_invoice_pdf_renderer] = lambda: fake_renderer

    user_repo = SQLUserRepository(db_session)
    await user_repo.save(User(email="admin@example.com", role=UserRole.ADMIN))

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as async_client:
            yield async_client
    finally:
        app.dependency_overrides = {}


async def _token(client: AsyncClient, email: str = "admin@example.com") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.cookies["auth_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_order(db_session, code: str = "TPPDF01") -> str:
    order_id = f"ord-{code.lower()}"
    db_session.add(
        OrderORM(
            id=order_id,
            customer_id="cust-1",
            code=code,
            status="entregado",
            date=datetime.datetime(2026, 11, 11, 12, 0, tzinfo=datetime.UTC),
            payment_method="cash",
            delivery_mode="pickup",
            delivery_address="",
            customer_name="Maria",
        )
    )
    await db_session.commit()
    return order_id


async def _seed_invoice(
    db_session,
    order_id: str,
    *,
    estado: str = "A",
    with_settings: bool = True,
) -> str:
    repo = SQLInvoiceRepository(db_session)
    invoice = _invoice(order_id, estado=estado)
    item = InvoiceItem(
        descripcion="Torta de limon",
        cantidad=Decimal(2),
        precio_unit="2600.00",
        position=1,
    )
    await repo.save_invoice(invoice, [item])
    if with_settings:
        await repo.save_settings(SETTINGS)
    await db_session.commit()
    return invoice.id


async def test_pdf_admin_ok(client, db_session, fake_renderer):
    order_id = await _seed_order(db_session)
    invoice_id = await _seed_invoice(db_session, order_id)
    token = await _token(client)

    response = await client.get(
        f"/api/v1/invoices/{invoice_id}/pdf", headers=_auth(token)
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="FACTURA_0001-00000007.pdf"'
    )
    assert response.content.startswith(b"%PDF")
    assert len(fake_renderer.payloads) == 1
    payload = fake_renderer.payloads[0]
    assert payload["emisor"]["cuit"] == "30123456789"
    assert payload["emisor"]["categoria_monotributo"] == "F"
    assert payload["comprobante"]["cae"] == CAE
    assert payload["comprobante"]["imp_total"] == "5200.00"
    assert payload["comprobante"]["receptor"]["doc_tipo"] == 99
    assert payload["comprobante"]["items"][0]["precio_unit"] == "2600.00"
    assert payload["comprobante"]["items"][0]["cantidad"] == 2.0


async def test_pdf_404_si_no_existe(client):
    token = await _token(client)

    response = await client.get("/api/v1/invoices/no-existe/pdf", headers=_auth(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "comprobante_no_encontrado"


async def test_pdf_409_si_el_comprobante_no_esta_aprobado(
    client, db_session, fake_renderer
):
    order_id = await _seed_order(db_session, code="TPPDF02")
    invoice_id = await _seed_invoice(db_session, order_id, estado=ESTADO_RECHAZADO)
    token = await _token(client)

    response = await client.get(
        f"/api/v1/invoices/{invoice_id}/pdf", headers=_auth(token)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "comprobante_no_aprobado"
    assert fake_renderer.payloads == []


async def test_pdf_503_sin_settings(client, db_session, fake_renderer):
    order_id = await _seed_order(db_session, code="TPPDF03")
    invoice_id = await _seed_invoice(db_session, order_id, with_settings=False)
    token = await _token(client)

    response = await client.get(
        f"/api/v1/invoices/{invoice_id}/pdf", headers=_auth(token)
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "invoicing_not_configured"
    assert fake_renderer.payloads == []


async def test_pdf_503_si_pdfgenerator_falla(client, db_session, fake_renderer):
    order_id = await _seed_order(db_session, code="TPPDF04")
    invoice_id = await _seed_invoice(db_session, order_id)
    fake_renderer.error = PdfServiceError("pdfgenerator no responde")
    token = await _token(client)

    response = await client.get(
        f"/api/v1/invoices/{invoice_id}/pdf", headers=_auth(token)
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")

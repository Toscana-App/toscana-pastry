"""T4 — API de facturación ARCA (emisión, registro y settings).

Cliente AFIP fake: cero red. Corre igual en local (sqlite) y en CI (Postgres).
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
from domain.invoicing import (
    AfipCaeResult,
    AfipCredentialMissingError,
    AfipUnavailableError,
)
from domain.models import User, UserRole
from main import app

CAE = "75123456789012"
SETTINGS = {
    "cuit": "30123456789",
    "punto_venta": 3,
    "razon_social": "PASTELERIA TOSCANA",
    "domicilio": "Av. Corrientes 123",
    "condicion_iva": "Responsable Monotributo",
    "categoria_monotributo": "F",
    "ingresos_brutos": "Exento",
    "inicio_actividades": "01/05/2020",
}


class FakeAfipClient:
    def __init__(self) -> None:
        self.ultimo = 6
        self.resultado = "A"
        self.cae = CAE
        self.cae_vto = datetime.date(2026, 11, 21)
        self.observaciones: tuple[str, ...] = ()
        self.error: Exception | None = None
        self.last_authorized_calls: list[tuple[str, int, int]] = []
        self.cae_requests: list[dict] = []

    async def last_authorized(
        self, *, cuit: str, punto_venta: int, tipo_cbte: int
    ) -> int:
        self.last_authorized_calls.append((cuit, punto_venta, tipo_cbte))
        if self.error is not None:
            raise self.error
        return self.ultimo

    async def request_cae(self, *, cuit: str, request: dict) -> AfipCaeResult:
        self.cae_requests.append({"cuit": cuit, "request": request})
        if self.error is not None:
            raise self.error
        if self.resultado == "A":
            self.ultimo = request["FeDetReq"]["FECAEDetRequest"][0]["CbteDesde"]
        return AfipCaeResult(
            resultado=self.resultado,
            cae=self.cae,
            cae_vto=self.cae_vto,
            observaciones=self.observaciones,
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


@pytest.fixture
def fake_afip() -> FakeAfipClient:
    return FakeAfipClient()


@pytest_asyncio.fixture
async def client(db_session, fake_afip):
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
    app.dependency_overrides[get_afip_client] = lambda: fake_afip

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


async def _token(client: AsyncClient, email: str = "admin@example.com") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.cookies["auth_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _put_settings(client: AsyncClient, **overrides) -> dict:
    token = await _token(client)
    payload = {**SETTINGS, **overrides}
    response = await client.put(
        "/api/v1/invoicing/settings", json=payload, headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()["settings"]


async def _seed_order(
    db_session,
    *,
    code: str = "TPINV01",
    quantity: int = 2,
    unit_price: str = "2600.00",
    discount: str | None = None,
) -> str:
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
            discount_amount=discount,
            customer_name="Maria",
        )
    )
    db_session.add(
        OrderItemORM(
            id=f"item-{code.lower()}",
            order_id=order_id,
            product_id="prod-1",
            product_name="Torta de limon",
            quantity=quantity,
            unit_price=unit_price,
            portion_note="",
            qty=quantity,
            portions=20,
            note="",
            position=1,
        )
    )
    await db_session.commit()
    return order_id


def _payload(order_id: str, **overrides) -> dict:
    payload = {
        "order_id": order_id,
        "concepto": 1,
        "doc_tipo": 99,
        "doc_nro": 0,
        "receptor_nombre": "Juan Perez",
    }
    payload.update(overrides)
    return payload


async def _emit(client: AsyncClient, order_id: str, **overrides):
    token = await _token(client)
    return await client.post(
        "/api/v1/invoices", json=_payload(order_id, **overrides), headers=_auth(token)
    )


class TestEmision:
    async def test_crea_la_factura(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)

        response = await _emit(client, order_id)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["order_id"] == order_id
        assert body["punto_venta"] == 3
        assert body["tipo_cbte"] == 11
        assert body["numero"] == 7
        assert body["cae"] == CAE
        assert body["cae_vto"] == "2026-11-21"
        assert body["estado"] == "A"
        assert body["imp_total"] == 520000
        assert body["pdf_url"] == f"/api/v1/invoices/{body['id']}/pdf"
        assert datetime.date.fromisoformat(body["fecha"])

    async def test_imp_total_es_el_neto_del_pedido(self, client, db_session, fake_afip):
        order_id = await _seed_order(
            db_session, quantity=3, unit_price="1500.50", discount="200.50"
        )
        await _put_settings(client)

        response = await _emit(
            client,
            order_id,
            items=[{"descripcion": "Torta", "cantidad": 1, "precio_unit": 1}],
        )

        assert response.status_code == 201, response.text
        assert response.json()["imp_total"] == 430100

    async def test_usa_cuit_y_punto_de_venta_de_settings(
        self, client, db_session, fake_afip
    ):
        order_id = await _seed_order(db_session)
        await _put_settings(client)

        await _emit(client, order_id)

        assert fake_afip.last_authorized_calls == [("30123456789", 3, 11)]
        request = fake_afip.cae_requests[0]["request"]
        assert request["FeCabReq"] == {"CantReg": 1, "PtoVta": 3, "CbteTipo": 11}
        detalle = request["FeDetReq"]["FECAEDetRequest"][0]
        assert detalle["ImpTotal"] == 5200.0
        assert detalle["ImpNeto"] == 5200.0
        assert detalle["DocTipo"] == 99
        assert detalle["DocNro"] == 0

    async def test_concepto_servicios_envia_periodo(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        hoy = datetime.date.today()

        response = await _emit(
            client,
            order_id,
            concepto=2,
            fch_serv_desde=hoy.isoformat(),
            fch_serv_hasta=hoy.isoformat(),
        )

        assert response.status_code == 201, response.text
        detalle = fake_afip.cae_requests[0]["request"]["FeDetReq"]["FECAEDetRequest"][0]
        assert detalle["Concepto"] == 2
        assert detalle["FchServDesde"] == hoy.strftime("%Y%m%d")

    async def test_persiste_items_del_payload(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        token = await _token(client)

        response = await client.post(
            "/api/v1/invoices",
            json=_payload(
                order_id,
                items=[
                    {"descripcion": "Bizmerengue", "cantidad": 20, "precio_unit": 260000},
                    {"descripcion": "Ensalada", "cantidad": 2, "precio_unit": 10050},
                ],
            ),
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        invoice_id = response.json()["id"]

        detail = await client.get(f"/api/v1/invoices/{invoice_id}", headers=_auth(token))
        assert detail.status_code == 200, detail.text
        items = detail.json()["items"]
        assert [item["descripcion"] for item in items] == ["Bizmerengue", "Ensalada"]
        assert items[0]["cantidad"] == 20
        assert items[0]["precio_unit"] == 260000

    async def test_pedido_inexistente_404(self, client, db_session, fake_afip):
        await _put_settings(client)
        response = await _emit(client, "ord-inexistente")
        assert response.status_code == 404

    async def test_pedido_ya_facturado_409(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        first = await _emit(client, order_id)
        assert first.status_code == 201

        second = await _emit(client, order_id)

        assert second.status_code == 409
        body = second.json()
        assert body["detail"] == "pedido_ya_facturado"
        assert body["existing_invoice"]["id"] == first.json()["id"]
        assert body["existing_invoice"]["numero"] == first.json()["numero"]
        assert len(fake_afip.cae_requests) == 1

    async def test_concepto_servicios_sin_fechas_422(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        response = await _emit(client, order_id, concepto=2)
        assert response.status_code == 422
        assert response.json()["detail"] == "periodo_servicio_requerido"

    async def test_doc_tipo_invalido_422(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        response = await _emit(client, order_id, doc_tipo=97)
        assert response.status_code == 422

    async def test_campo_extra_422(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        response = await _emit(client, order_id, importe_total=1)
        assert response.status_code == 422

    async def test_sin_settings_503(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        response = await _emit(client, order_id)
        assert response.status_code == 503
        assert response.json()["detail"] == "invoicing_not_configured"
        assert fake_afip.cae_requests == []

    async def test_credenciales_faltantes_503(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        fake_afip.error = AfipCredentialMissingError("afip_credential_missing")

        response = await _emit(client, order_id)

        assert response.status_code == 503
        assert response.json()["detail"] == "afip_credential_missing"

    async def test_arca_caido_503(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        fake_afip.error = AfipUnavailableError("afip_unavailable")

        response = await _emit(client, order_id)

        assert response.status_code == 503
        assert response.json()["detail"] == "afip_unavailable"

    async def test_rechazo_arca_400_con_observaciones_saneadas(
        self, client, db_session, fake_afip
    ):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        fake_afip.resultado = "R"
        fake_afip.cae = ""
        fake_afip.cae_vto = None
        fake_afip.observaciones = (
            "10015: Fecha fuera de rango",
            "Traceback (most recent call last): /run/secrets/afip_key.pem",
        )

        response = await _emit(client, order_id)

        assert response.status_code == 400
        body = response.json()
        assert body["detail"] == "comprobante_rechazado"
        assert body["observaciones"] == ["10015: Fecha fuera de rango"]
        token = await _token(client)
        listed = await client.get("/api/v1/invoices", headers=_auth(token))
        assert listed.json()["total"] == 0


class TestRegistro:
    async def test_lista_y_filtra_por_pedido(self, client, db_session, fake_afip):
        await _put_settings(client)
        o1 = await _seed_order(db_session, code="TPINV01")
        o2 = await _seed_order(db_session, code="TPINV02")
        await _emit(client, o1)
        await _emit(client, o2)
        token = await _token(client)

        todo = await client.get("/api/v1/invoices", headers=_auth(token))
        assert todo.status_code == 200
        assert todo.json()["total"] == 2
        assert todo.json()["page"] == 1
        assert todo.json()["page_size"] == 20

        solo = await client.get(
            f"/api/v1/invoices?order_id={o2}", headers=_auth(token)
        )
        assert solo.json()["total"] == 1
        assert solo.json()["items"][0]["order_id"] == o2
        assert solo.json()["items"][0]["imp_total"] == 520000

    async def test_paginacion(self, client, db_session, fake_afip):
        await _put_settings(client)
        for index in range(1, 4):
            order_id = await _seed_order(db_session, code=f"TPINV0{index}")
            await _emit(client, order_id)
        token = await _token(client)

        page1 = await client.get(
            "/api/v1/invoices?page=1&page_size=2", headers=_auth(token)
        )
        page2 = await client.get(
            "/api/v1/invoices?page=2&page_size=2", headers=_auth(token)
        )

        assert len(page1.json()["items"]) == 2
        assert len(page2.json()["items"]) == 1
        assert page1.json()["total"] == 3

    async def test_detalle(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        created = await _emit(
            client,
            order_id,
            items=[{"descripcion": "Torta", "cantidad": 2, "precio_unit": 260000}],
        )
        token = await _token(client)

        response = await client.get(
            f"/api/v1/invoices/{created.json()['id']}", headers=_auth(token)
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["invoice"]["numero"] == 7
        assert body["invoice"]["cae"] == CAE
        assert body["invoice"]["receptor_nombre"] == "Juan Perez"
        assert body["invoice"]["imp_total"] == 520000
        assert len(body["items"]) == 1
        assert body["observaciones"] == []

    async def test_detalle_inexistente_404(self, client):
        token = await _token(client)
        response = await client.get("/api/v1/invoices/nope", headers=_auth(token))
        assert response.status_code == 404


class TestSettings:
    async def test_sin_configurar(self, client):
        token = await _token(client)
        response = await client.get("/api/v1/invoicing/settings", headers=_auth(token))
        assert response.status_code == 200
        assert response.json() == {"configured": False, "settings": None}

    async def test_put_y_get(self, client):
        saved = await _put_settings(client)
        assert saved["cuit"] == "30123456789"
        assert saved["punto_venta"] == 3
        assert saved["categoria_monotributo"] == "F"

        token = await _token(client)
        response = await client.get("/api/v1/invoicing/settings", headers=_auth(token))
        assert response.json()["configured"] is True
        assert response.json()["settings"]["razon_social"] == "PASTELERIA TOSCANA"

    async def test_put_normaliza_categoria(self, client):
        saved = await _put_settings(client, categoria_monotributo="a")
        assert saved["categoria_monotributo"] == "A"

    async def test_cuit_invalido_422(self, client):
        token = await _token(client)
        response = await client.put(
            "/api/v1/invoicing/settings",
            json={**SETTINGS, "cuit": "123"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_categoria_invalida_422(self, client):
        token = await _token(client)
        response = await client.put(
            "/api/v1/invoicing/settings",
            json={**SETTINGS, "categoria_monotributo": "Z"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_inicio_actividades_invalido_422(self, client):
        token = await _token(client)
        response = await client.put(
            "/api/v1/invoicing/settings",
            json={**SETTINGS, "inicio_actividades": "2020-05-01"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_campo_extra_422(self, client):
        token = await _token(client)
        response = await client.put(
            "/api/v1/invoicing/settings",
            json={**SETTINGS, "certificado": "x"},
            headers=_auth(token),
        )
        assert response.status_code == 422


class TestDetallePedido:
    async def test_incluye_la_factura(self, client, db_session, fake_afip):
        order_id = await _seed_order(db_session)
        await _put_settings(client)
        created = await _emit(client, order_id)
        token = await _token(client)

        response = await client.get(f"/api/v1/orders/{order_id}", headers=_auth(token))

        assert response.status_code == 200, response.text
        invoice = response.json()["invoice"]
        assert invoice == {
            "numero": 7,
            "cae": CAE,
            "cae_vto": "2026-11-21",
            "pdf_url": f"/api/v1/invoices/{created.json()['id']}/pdf",
        }

    async def test_sin_factura_es_null(self, client, db_session):
        order_id = await _seed_order(db_session)
        token = await _token(client)

        response = await client.get(f"/api/v1/orders/{order_id}", headers=_auth(token))

        assert response.status_code == 200, response.text
        assert response.json()["invoice"] is None

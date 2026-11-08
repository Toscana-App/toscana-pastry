"""PDF de presupuesto (Fase 8, P9) + WhatsApp outbound (P10): API.

Cubre:
- GET /budgets/{id}/pdf: PDF (pdfgenerator, ADR-0001), ETag por hash,
  304, regeneración tras edición, sin auth 401.
- POST /budgets/{id}/pdf: link firmado 72 h; admin-only.
- GET /pdf/{token}: público; token inválido/alterado/vencido → 404.
- Seguridad: el snapshot enviado a pdfgenerator no contiene
  costo/ganancia/margen.
- POST /budgets/{id}/whatsapp-link: wa.me E.164, plantilla con ítems y
  total, registro auditado (teléfono enmascarado), 400 con teléfono
  inválido, 429 al pasar el límite de 30/día.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from api.v1.pdf.router import public_pdf_limiter
from data.models import Base, BudgetEventORM
from data.accent import accent_fold
from data.db import get_db
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.repositories.sql_customer_repository import SQLCustomerRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_budget_repository import SQLBudgetRepository
from data.repositories.sql_document_repository import SQLDocumentRepository
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
)
from api.v1.budgets.dependencies import get_budget_repository
from api.v1.pdf.dependencies import get_document_repository
from api.v1.pdf.signing import make_share_token
from core.config import settings as app_settings
from domain.models import User, UserRole

PDF_MAGIC = b"%PDF"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
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

    async def override_get_customer_repository():
        yield SQLCustomerRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    async def override_get_budget_repository():
        yield SQLBudgetRepository(db_session)

    async def override_get_document_repository():
        yield SQLDocumentRepository(db_session)

    public_pdf_limiter.reset()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_customer_repository] = override_get_customer_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    app.dependency_overrides[get_budget_repository] = override_get_budget_repository
    app.dependency_overrides[get_document_repository] = override_get_document_repository
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


async def _login(client: AsyncClient, email: str = "admin@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email}
    )
    assert response.status_code == 200, response.text
    return response.cookies["auth_token"]


async def _setup(client: AsyncClient, token: str):
    """Settings (150/h, margen 100%), harina 2.800/kg, torta de limón
    (250g, 30 min, 6 porciones). Costo torta: 775 -> venta 1.550."""
    response = await client.put(
        "/api/v1/tenant/settings",
        json={
            "hourly_rate": 15000,
            "margin_pct": "100",
            "round_step": 500,
            "include_labor": True,
            "include_gas": False,
            "gas_pct": "0",
            "include_waste": False,
            "waste_pct": "0",
            "urgent_surcharge_pct": "0",
            "default_prep_minutes": 30,
            "default_servings": 6,
            "default_difficulty": "simple",
            "business_name": "Toscana Pastry",
            "footer_text": "Pedidos: (0357) 123-4567",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        "/api/v1/ingredients",
        json={
            "name": "Harina",
            "unit": "kg",
            "price_per_unit": 280000,
            "stock_qty": 0,
            "low_stock_threshold": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    flour_id = response.json()["id"]

    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta de Limón",
            "category": "Tortas",
            "description": "Torta clásica",
            "recipe": [{"ingredient_id": flour_id, "qty": "250", "unit": "g"}],
            "prep_time_min": 30,
            "servings": 6,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _make_customer(
    client: AsyncClient, token: str, name: str, phone: str,
    delivery_address: str | None = None,
) -> str:
    body: dict = {"name": name, "phone": phone}
    if delivery_address is not None:
        body["delivery_address"] = delivery_address
    response = await client.post(
        "/api/v1/customers",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _make_budget(
    client: AsyncClient,
    token: str,
    customer_id: str,
    product_id: str,
    qty: int = 2,
) -> str:
    response = await client.post(
        "/api/v1/budgets",
        json={
            "customer_id": customer_id,
            "calculation_mode": "cost_plus",
            "margin_pct": "100",
            "items": [{"product_id": product_id, "qty": qty}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestBudgetPdfEndpoint:
    async def test_get_pdf_devuelve_pdf_valido(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "María", "+54 9 357 123-4567"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)

        response = await client.get(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content[:4] == PDF_MAGIC
        assert response.headers["etag"]
        disposition = response.headers["content-disposition"]
        assert "attachment" in disposition
        assert "presupuesto_00001.pdf" in disposition

    async def test_get_pdf_304_con_etag(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)
        headers = {"Authorization": f"Bearer {token}"}

        first = await client.get(f"/api/v1/budgets/{budget_id}/pdf", headers=headers)
        assert first.status_code == 200
        etag = first.headers["etag"]

        second = await client.get(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={**headers, "if-none-match": etag},
        )
        assert second.status_code == 304

    async def test_editar_el_presupuesto_regenera_el_pdf(self, client, pdf_fake):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)
        headers = {"Authorization": f"Bearer {token}"}

        first = await client.get(f"/api/v1/budgets/{budget_id}/pdf", headers=headers)
        etag_1 = first.headers["etag"]

        # Edición: cantidad 2 -> 3 (hash de contenido nuevo).
        response = await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"items": [{"product_id": product_id, "qty": 3}]},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        second = await client.get(f"/api/v1/budgets/{budget_id}/pdf", headers=headers)
        assert second.status_code == 200
        assert second.headers["etag"] != etag_1
        # El snapshot enviado a pdfgenerator refleja la nueva cantidad (3 x 1550).
        assert pdf_fake.last_budget_payload["items"][0]["qty"] == 3
        assert pdf_fake.last_budget_payload["items"][0]["line_selling"] == "4650.00"

    async def test_get_pdf_sin_auth_es_401(self, client):
        assert (await client.get("/api/v1/budgets/cualquiera/pdf")).status_code == 401

    async def test_pdf_no_expose_costos_ni_ganancia(self, client, pdf_fake):
        """Seguridad de P9: el documento del cliente no contiene los
        números internos (costo unitario 775, ganancia 1.000, ni las
        palabras costo/ganancia/margen)."""
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)

        response = await client.get(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        payload = pdf_fake.last_budget_payload
        # Ni las palabras internas como claves del snapshot.
        internal = {"costo", "ganancia", "margen", "unit_cost"}
        assert not internal & set(payload.keys())
        for item in payload["items"]:
            assert not internal & set(item.keys())
        # Ni los números internos como valores (costo 775, ganancia 1000).
        values = [str(v) for k, v in payload.items() if k != "items"]
        for item in payload["items"]:
            values.extend(str(v) for v in item.values())
        assert "775" not in values
        assert "1000" not in values
        # El precio de venta (1550) SÍ se envía.
        assert "1550.00" in values

    async def test_pdf_incluye_direccion_de_entrega(self, client, pdf_fake):
        """RF-P7-07: el documento muestra la direccion del snapshot si
        esta presente."""
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client,
            token,
            "María",
            "+54 9 357 123-4567",
            delivery_address="Calle Falsa 1234, San Francisco",
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)
        response = await client.get(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        assert pdf_fake.last_budget_payload["delivery_address"] == "Calle Falsa 1234, San Francisco"

    async def test_pdf_sin_direccion_no_muestra_la_linea(self, client, pdf_fake):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)
        response = await client.get(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pdf_fake.last_budget_payload["delivery_address"] is None


class TestShareLink:
    async def test_post_share_devuelve_link_firmado(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)

        response = await client.post(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["url"].startswith(
            f"{app_settings.PUBLIC_BASE_URL}/api/v1/pdf/"
        )
        token_part = body["url"].rsplit("/", 1)[-1]
        assert token_part.count(".") == 1  # payload.firma
        # TTL 72 h: expira entre 71 y 72 h desde ahora.
        expires = datetime.fromisoformat(body["expires_at"])
        delta = expires - datetime.now(timezone.utc)
        assert timedelta(hours=71) < delta < timedelta(hours=72)

    async def test_link_publico_devuelve_el_pdf(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(client, token, "María", "5493571234567")
        budget_id = await _make_budget(client, token, customer_id, product_id)
        share = await client.post(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        url = share.json()["url"]
        path = url.replace(app_settings.PUBLIC_BASE_URL, "")

        # SIN autenticación: el token es la credencial.
        response = await client.get(path)
        assert response.status_code == 200
        assert response.content[:4] == PDF_MAGIC
        assert "inline" in response.headers["content-disposition"]

    @pytest.mark.parametrize(
        "tamper",
        [
            lambda t: t[:-2] + "xx",      # firma alterada
            lambda t: t.split(".")[0] + ".AAAA",  # firma invalida
            lambda t: "token-sin-punto",
        ],
    )
    async def test_token_invalido_es_404(self, client, tamper):
        valid, _ = make_share_token("cualquier-id", app_settings.SECRET_KEY)
        response = await client.get(f"/api/v1/pdf/{tamper(valid)}")
        assert response.status_code == 404

    def test_token_usa_subclave_con_separacion_de_dominio(self):
        import hashlib
        import hmac

        from api.v1.pdf.signing import verify_share_token

        token, _ = make_share_token("b1", "secreto")
        assert verify_share_token(token, "secreto") == "b1"
        assert verify_share_token(token, "otro") is None
        # Un token firmado directamente con la SECRET_KEY (sin subclave,
        # p. ej. forjado con la clave del JWT) no es válido.
        import base64

        payload = b"v1|b1|9999999999"
        sig = hmac.new(b"secreto", payload, hashlib.sha256).digest()
        b64 = lambda d: base64.urlsafe_b64encode(d).decode().rstrip("=")
        assert verify_share_token(f"{b64(payload)}.{b64(sig)}", "secreto") is None

    def test_token_sin_version_en_el_payload_es_invalido(self):
        import base64
        import hashlib
        import hmac

        from api.v1.pdf.signing import _signing_key, verify_share_token

        payload = b"b1|9999999999"
        sig = hmac.new(_signing_key("secreto"), payload, hashlib.sha256).digest()
        b64 = lambda d: base64.urlsafe_b64encode(d).decode().rstrip("=")
        assert verify_share_token(f"{b64(payload)}.{b64(sig)}", "secreto") is None

    async def test_endpoint_publico_tiene_rate_limit_por_ip(self, client):
        for _ in range(public_pdf_limiter.max_requests):
            response = await client.get("/api/v1/pdf/token-sin-punto")
            assert response.status_code == 404
        response = await client.get("/api/v1/pdf/token-sin-punto")
        assert response.status_code == 429

    async def test_token_vencido_es_404(self, client):
        expired, _ = make_share_token(
            "cualquier-id", app_settings.SECRET_KEY, ttl_seconds=-10
        )
        response = await client.get(f"/api/v1/pdf/{expired}")
        assert response.status_code == 404

    async def test_share_solo_admin(self, client):
        admin_token = await _login(client)
        product_id = await _setup(client, admin_token)
        customer_id = await _make_customer(
            client, admin_token, "María", "5493571234567"
        )
        budget_id = await _make_budget(
            client, admin_token, customer_id, product_id
        )
        customer_token = await _login(client, "customer@example.com")
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/pdf",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403


class TestWhatsAppLink:
    async def test_whatsapp_link_con_plantilla(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "María", "0357 422-3456"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)

        response = await client.post(
            f"/api/v1/budgets/{budget_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # E.164 desde formato local (0357...).
        assert body["url"].startswith("https://wa.me/543574223456?text=")
        # Registro de auditoría (RF-P10-02).
        datetime.fromisoformat(body["sent_at"])
        # Plantilla (RF-P10-01): saludo, ítems, total, firma, link PDF.
        message = unquote(body["url"].split("text=", 1)[1])
        assert "Hola María:" in message
        assert "Torta de Limón" in message
        assert "$3.100,00" in message
        assert "Total: $3.100,00" in message
        assert "IVA (21%): $651,00 — costo aparte del total" in message
        assert "/api/v1/pdf/" in message
        assert "Toscana Pastry" in message

    async def test_whatsapp_link_incluye_direccion_de_entrega(self, client):
        """RF-P7-07: el mensaje muestra la direccion si esta presente en
        el snapshot del presupuesto."""
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client,
            token,
            "María",
            "0357 422-3456",
            delivery_address="Calle Falsa 1234, San Francisco",
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        message = unquote(response.json()["url"].split("text=", 1)[1])
        assert "Calle Falsa 1234" in message

    async def test_whatsapp_link_teléfono_invalido_es_400(self, client):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "Corto", "123456"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        # RNF-P10-05: el teléfono no se devuelve en `detail`.
        assert "123456" not in response.text

    async def test_evento_registrado_con_telefono_enmascarado(self, client, db_session):
        from sqlalchemy import select

        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "María", "5493571234567"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        events = (
            (
                await db_session.execute(
                    select(BudgetEventORM).where(
                        BudgetEventORM.budget_id == budget_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].type == "whatsapp_sent"
        # RNF-P10-05: el teléfono completo NO se registra.
        assert "5493571234567" not in events[0].payload
        assert events[0].payload == "+54 ** ****67"

    async def test_límite_diario_30_es_429(self, client, db_session):
        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "María", "5493571234567"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)

        # 30 envíos previos, todos dentro de la ventana de 24 h.
        now = datetime.now(timezone.utc)
        for i in range(30):
            db_session.add(
                BudgetEventORM(
                    id=f"evt-{i}",
                    budget_id=budget_id,
                    type="whatsapp_sent",
                    payload="+54 ** ****00",
                    created_at=now - timedelta(minutes=i * 30),
                )
            )
        await db_session.commit()

        response = await client.post(
            f"/api/v1/budgets/{budget_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 429

    async def test_limite_atomico_registra_el_30_y_rechaza_el_31(
        self, client, db_session
    ):
        from sqlalchemy import func, select

        token = await _login(client)
        product_id = await _setup(client, token)
        customer_id = await _make_customer(
            client, token, "María", "5493571234567"
        )
        budget_id = await _make_budget(client, token, customer_id, product_id)
        now = datetime.now(timezone.utc)
        for i in range(29):
            db_session.add(
                BudgetEventORM(
                    id=f"evt-{i}",
                    budget_id=budget_id,
                    type="whatsapp_sent",
                    payload="+54 ** ****00",
                    created_at=now - timedelta(minutes=i),
                )
            )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"/api/v1/budgets/{budget_id}/whatsapp-link"

        assert (await client.post(url, headers=headers)).status_code == 200
        assert (await client.post(url, headers=headers)).status_code == 429
        total = (
            await db_session.execute(
                select(func.count())
                .select_from(BudgetEventORM)
                .where(BudgetEventORM.type == "whatsapp_sent")
            )
        ).scalar_one()
        assert total == 30

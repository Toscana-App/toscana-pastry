"""Presupuestos (Fase 7, P7/P8): API end-to-end.

Fixture por test: settings (150/h, margen 100%, mano de obra encendida),
harina 2.800/kg, torta de limón (250g, 30 min, 6 porciones).
Costo de una torta: 700 (harina) + 75 (mano) = 775; margen 100% -> 1.550.

Flujo: wizard -> borrador #000NN -> editar/recalcular -> enviar (version)
-> convertir a pedido -> borrar. Money en centavos (RF-P8-03).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from data.models import Base
from data.accent import accent_fold
from data.db import get_db
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.repositories.sql_customer_repository import SQLCustomerRepository
from data.repositories.sql_order_repository import SQLOrderRepository
from data.repositories.sql_budget_repository import SQLBudgetRepository
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
from domain.models import User, UserRole


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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_customer_repository] = override_get_customer_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    app.dependency_overrides[get_budget_repository] = override_get_budget_repository
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
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
    return response.json()["access_token"]


async def _customer_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "customer@example.com"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def _set_settings(client: AsyncClient, token: str) -> None:
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
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


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


async def _make_flour(client: AsyncClient, token: str, price: int = 280000) -> str:
    response = await client.post(
        "/api/v1/ingredients",
        json={
            "name": "Harina",
            "unit": "kg",
            "price_per_unit": price,
            "stock_qty": 0,
            "low_stock_threshold": 0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _make_torta(
    client: AsyncClient, token: str, flour_id: str
) -> str:
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta de Limón",
            "category": "Tortas",
            "description": "Torta clásica",
            "recipe": [
                {"ingredient_id": flour_id, "qty": "250", "unit": "g"}
            ],
            "prep_time_min": 30,
            "servings": 6,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _setup(client: AsyncClient):
    token = await _admin_token(client)
    await _set_settings(client, token)
    flour_id = await _make_flour(client, token)
    torta_id = await _make_torta(client, token, flour_id)
    customer_id = await _make_customer(
        client, token, "María", "+357 555-1234"
    )
    return token, flour_id, torta_id, customer_id


async def _create_budget(
    client: AsyncClient,
    token: str,
    customer_id: str,
    torta_id: str,
    qty: int = 2,
    margin_pct: str | None = None,
    mode: str | None = None,
    price_override: int | None = None,
) -> dict:
    item: dict = {"product_id": torta_id, "qty": qty}
    if price_override is not None:
        item["price_override"] = price_override
    body: dict = {"customer_id": customer_id, "items": [item]}
    if margin_pct is not None:
        body["margin_pct"] = margin_pct
    if mode is not None:
        body["calculation_mode"] = mode
    response = await client.post(
        "/api/v1/budgets",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _send(client: AsyncClient, token: str, budget_id: str) -> None:
    response = await client.post(
        f"/api/v1/budgets/{budget_id}/send",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


async def _list(client: AsyncClient, token: str, **params) -> dict:
    response = await client.get(
        "/api/v1/budgets",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Creacion (P7)
# ---------------------------------------------------------------------------


class TestBudgetCreate:
    async def test_crea_borrador_con_secuencia_y_totales(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=2)

        assert body["status"] == "borrador"
        assert body["seq"] == "#00001"
        assert body["version"] == 0
        assert body["calculation_mode"] == "cost_plus"
        assert body["margin_pct"] is None
        assert body["customer"]["name"] == "María"
        assert body["customer"]["phone"] == "3575551234"
        assert body["sent_at"] is None

        item = body["items"][0]
        assert item["product_name"] == "Torta de Limón"
        assert item["qty"] == 2
        assert item["unit_cost"] == 77500  # 700 + 75
        assert item["unit_selling"] == 155000  # margen 100%
        assert item["line_cost"] == 155000
        assert item["line_selling"] == 310000
        assert item["price_overridden"] is False

        summary = body["summary"]
        assert summary["subtotal"] == 310000
        assert summary["total_costos"] == 155000
        assert summary["ganancia"] == 155000
        assert summary["total_venta"] == 375100  # 3100 * 1.21

    async def test_segunda_secuencia_no_reutiliza(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        first = await _create_budget(client, token, customer_id, torta_id)
        second = await _create_budget(client, token, customer_id, torta_id)
        assert first["seq"] == "#00001"
        assert second["seq"] == "#00002"

    async def test_margin_override(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id, qty=1, margin_pct="200"
        )
        assert body["margin_pct"] == "200"
        assert body["items"][0]["unit_selling"] == 232500  # 775 * 3
        assert body["summary"]["subtotal"] == 232500

    async def test_modos_manual_con_override(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id,
            qty=1, mode="manual", price_override=200000,
        )
        item = body["items"][0]
        assert item["unit_cost"] == 77500
        assert item["unit_selling"] == 200000
        assert item["price_overridden"] is True
        assert body["summary"]["ganancia"] == 122500

    async def test_manual_sin_override_usa_cost_plus(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id, qty=1, mode="manual"
        )
        assert body["items"][0]["unit_selling"] == 155000
        assert body["items"][0]["price_overridden"] is False

    async def test_ganancia_negativa_permitida(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id,
            qty=1, mode="manual", price_override=50000,
        )
        assert body["summary"]["ganancia"] == -27500
        assert body["summary"]["total_venta"] == 60500  # 500 * 1.21

    async def test_cliente_desconocido_da_404(self, client: AsyncClient):
        token, _, torta_id, _ = await _setup(client)
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": "no-existe",
                "items": [{"product_id": torta_id, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_producto_desconocido_da_400(self, client: AsyncClient):
        token, _, _, customer_id = await _setup(client)
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "items": [{"product_id": "no-existe", "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_items_vacios_da_422(self, client: AsyncClient):
        token, _, _, customer_id = await _setup(client)
        response = await client.post(
            "/api/v1/budgets",
            json={"customer_id": customer_id, "items": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_alta_requiere_admin(self, client: AsyncClient):
        _, _, torta_id, customer_id = await _setup(client)
        token = await _customer_token(client)
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "items": [{"product_id": torta_id, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_leer_permitido_para_cliente(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.get(
            f"/api/v1/budgets/{body['id']}",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 200

    # -- delivery_address (RF-P7-06/07) --------------------------------

    async def test_crear_con_direccion_de_entrega(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "items": [{"product_id": torta_id, "qty": 2}],
                "delivery_address": "Av. San Martín 1234, San Francisco",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["delivery_address"] == (
            "Av. San Martín 1234, San Francisco"
        )

    async def test_crear_hereda_direccion_del_cliente(self, client: AsyncClient):
        """Sin direccion en el payload, el snapshot del presupuesto
        hereda la del cliente (RNF-P7-04)."""
        token, _, torta_id, _ = await _setup(client)
        customer_id = await _make_customer(
            client,
            token,
            "Con Direccion",
            "3575559999",
            delivery_address="Calle 27 de Febrero 500, San Francisco",
        )
        body = await _create_budget(client, token, customer_id, torta_id, qty=2)
        assert body["delivery_address"] == "Calle 27 de Febrero 500, San Francisco"

        detail = await client.get(
            f"/api/v1/budgets/{body['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        assert detail.json()["delivery_address"] == (
            "Calle 27 de Febrero 500, San Francisco"
        )

    async def test_crear_sin_direccion_da_null(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=2)
        assert body["delivery_address"] is None

    async def test_direccion_explicita_tiene_precedencia(
        self, client: AsyncClient
    ):
        token, _, torta_id, _ = await _setup(client)
        customer_id = await _make_customer(
            client,
            token,
            "Con Direccion",
            "3575559998",
            delivery_address="Calle Vieja 1",
        )
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "items": [{"product_id": torta_id, "qty": 2}],
                "delivery_address": "Calle Nueva 2",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["delivery_address"] == "Calle Nueva 2"


# ---------------------------------------------------------------------------
# Lectura pura (no vuelve al catalogo)
# ---------------------------------------------------------------------------


class TestBudgetRead:
    async def test_detalle_no_recuerda_catalogo(self, client: AsyncClient):
        token, flour_id, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=1)
        budget_id = body["id"]
        assert body["summary"]["subtotal"] == 155000

        # el catalogo cambia: sube el precio de la harina
        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 999900},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.get(
            f"/api/v1/budgets/{budget_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        # la lectura es pura: sigue mostrando lo guardado
        detail = response.json()
        assert detail["items"][0]["unit_cost"] == 77500
        assert detail["summary"]["subtotal"] == 155000

    async def test_get_no_encontrado_da_404(self, client: AsyncClient):
        token = await _admin_token(client)
        response = await client.get(
            "/api/v1/budgets/no-existe",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Edicion (borrador y enviado)
# ---------------------------------------------------------------------------


class TestBudgetUpdate:
    async def test_cambiar_qty_rederiva(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=1)
        budget_id = body["id"]

        response = await client.patch(
            f"/api/v1/budgets/{budget_id}/items",
            json={"items": [{"product_id": torta_id, "qty": 3}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        detail = response.json()
        assert detail["items"][0]["qty"] == 3
        assert detail["summary"]["subtotal"] == 465000

    async def test_put_margin_recuerda_precios(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=1)
        budget_id = body["id"]

        response = await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"margin_pct": "200"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        detail = response.json()
        assert detail["margin_pct"] == "200"
        assert detail["items"][0]["unit_selling"] == 232500
        assert detail["summary"]["subtotal"] == 232500

    async def test_editar_enviado_cambia_updated(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=1)
        budget_id = body["id"]
        await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"margin_pct": "150"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        detail = response.json()
        assert detail["status"] == "enviado"
        assert detail["version"] == 1  # la version la cambia el reenviar
        assert detail["items"][0]["unit_selling"] == 193750  # 775 * 2.5

    async def test_editar_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.put(
            f"/api/v1/budgets/{body['id']}",
            json={"margin_pct": "50"},
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403

    async def test_editar_no_encontrado_da_404(self, client: AsyncClient):
        token = await _admin_token(client)
        response = await client.put(
            "/api/v1/budgets/no-existe",
            json={"margin_pct": "50"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_editar_conserva_y_actualiza_direccion(self, client: AsyncClient):
        """PUT sin direccion conserva el snapshot; PUT con direccion
        explicito lo actualiza (RNF-P7-04)."""
        token, _, torta_id, customer_id = await _setup(client)
        created = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "items": [{"product_id": torta_id, "qty": 2}],
                "delivery_address": "Av. Corrientes 700, CABA",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 201
        budget_id = created.json()["id"]

        response = await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"items": [{"product_id": torta_id, "qty": 3}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["delivery_address"] == "Av. Corrientes 700, CABA"

        changed = await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"delivery_address": "Pasaje 12, San Francisco"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert changed.status_code == 200
        assert changed.json()["delivery_address"] == "Pasaje 12, San Francisco"


# ---------------------------------------------------------------------------
# Recalcular
# ---------------------------------------------------------------------------


class TestBudgetRecalculate:
    async def test_refleja_nuevos_precios_de_insumos(self, client: AsyncClient):
        token, flour_id, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=1)
        budget_id = body["id"]
        assert body["items"][0]["unit_cost"] == 77500

        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 999900},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/recalculate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        result = response.json()
        # 9999 * 0.25 = 2499.75 + 75 = 2574.75; margen 100% -> 5149.50
        assert result["summary"]["total_costos"] == 257475
        assert result["summary"]["subtotal"] == 514950
        assert result["margin_applied"] == "100"

        detail = await client.get(
            f"/api/v1/budgets/{budget_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["items"][0]["unit_cost"] == 257475

    async def test_recalcular_conserve_el_override_de_margen(
        self, client: AsyncClient
    ):
        token, flour_id, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id, qty=1, margin_pct="50"
        )
        budget_id = body["id"]
        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 560000},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/recalculate",
            headers={"Authorization": f"Bearer {token}"},
        )
        result = response.json()
        assert result["margin_applied"] == "50"
        # 1400 + 75 = 1475; margen 50% -> 2212.50
        assert result["summary"]["subtotal"] == 221250

    async def test_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/recalculate",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Enviar (RF-P8-05)
# ---------------------------------------------------------------------------


class TestBudgetSend:
    async def test_enviar_borrador_crea_version_1(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        budget_id = body["id"]

        response = await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        detail = response.json()
        assert detail["status"] == "enviado"
        assert detail["version"] == 1
        assert detail["sent_at"] is not None

    async def test_reenviar_sin_cambios_da_409(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        budget_id = body["id"]
        await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_reenviar_con_cambios_crea_version_2(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        budget_id = body["id"]
        await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.put(
            f"/api/v1/budgets/{budget_id}",
            json={"margin_pct": "150"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            f"/api/v1/budgets/{budget_id}/send",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        detail = response.json()
        assert detail["version"] == 2
        assert detail["status"] == "enviado"

    async def test_enviar_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/send",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Convertir a pedido (RF-P8-02)
# ---------------------------------------------------------------------------


class TestConvertToOrder:
    async def test_crea_pedido_nuevo_con_sus_snapshots(self, client: AsyncClient):
        token, flour_id, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id, qty=2)
        budget_id = body["id"]
        await _send(client, token, budget_id)

        response = await client.post(
            f"/api/v1/budgets/{budget_id}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["seq"] == "#00001"
        order_id = result["order_id"]

        # el pedido existe con el desglose congelado propio
        detail = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        order = detail.json()
        assert order["status"] == "nuevo"
        assert order["customer"]["name"] == "María"
        assert order["total"] == 310000  # 2 * 1550
        assert order["items"][0]["qty"] == 2
        assert order["items"][0]["complete"] is True

        # el catalogo cambia despues: el pedido (y el presupuesto) no se mueven
        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        order2 = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert order2.json()["total"] == 310000

    async def test_usa_el_margen_del_presupuesto(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id, qty=1, margin_pct="200"
        )
        await _send(client, token, body["id"])
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        order_id = response.json()["order_id"]
        detail = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["margin_pct"] == "200"
        assert detail.json()["total"] == 232500

    async def test_no_descuenta_stock(self, client: AsyncClient):
        token, flour_id, torta_id, customer_id = await _setup(client)
        # 10000g en stock
        await client.post(
            f"/api/v1/ingredients/{flour_id}/stock",
            json={"delta": "10000", "reason": "compra"},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = await _create_budget(client, token, customer_id, torta_id, qty=2)
        await _send(client, token, body["id"])
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        # el pedido sigue nuevo: sin confirmar, sin descuento
        detail = await client.get(
            f"/api/v1/ingredients/{flour_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["ingredient"]["stock_qty"] == "10000"

    async def test_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403


class TestMoneyContract:
    @pytest.mark.parametrize("bad", ["1500.00", 1500.5, True])
    async def test_price_override_no_entero_da_422(self, client: AsyncClient, bad):
        token, _, torta_id, customer_id = await _setup(client)
        response = await client.post(
            "/api/v1/budgets",
            json={
                "customer_id": customer_id,
                "calculation_mode": "manual",
                "items": [
                    {"product_id": torta_id, "qty": 1, "price_override": bad}
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestConvertRules:
    async def test_conserva_el_precio_manual(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(
            client, token, customer_id, torta_id, qty=2,
            mode="manual", price_override=2000,
        )
        await _send(client, token, body["id"])
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        detail = await client.get(
            f"/api/v1/orders/{response.json()['order_id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["total"] == 4000  # 2 * 2000, no 2 * 1550

    async def test_solo_enviado_es_convertible(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "budget_not_sent"

    async def test_segunda_conversion_da_409_already_converted(
        self, client: AsyncClient
    ):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        await _send(client, token, body["id"])
        url = f"/api/v1/budgets/{body['id']}/convert-to-order"
        headers = {"Authorization": f"Bearer {token}"}
        first = await client.post(url, headers=headers)
        assert first.status_code == 201
        second = await client.post(url, headers=headers)
        assert second.status_code == 409
        assert second.json()["detail"] == "already_converted"
        orders = await client.get("/api/v1/orders", headers=headers)
        assert orders.json()["total"] == 1

    async def test_persiste_order_id_en_el_presupuesto(
        self, client: AsyncClient, db_session
    ):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        await _send(client, token, body["id"])
        response = await client.post(
            f"/api/v1/budgets/{body['id']}/convert-to-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        stored = await SQLBudgetRepository(db_session).get(body["id"])
        assert stored is not None
        assert stored.order_id == response.json()["order_id"]


# ---------------------------------------------------------------------------
# Borrado
# ---------------------------------------------------------------------------


class TestBudgetDelete:
    async def test_borra_y_secuencia_no_se_reutiliza(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        budget_id = body["id"]

        response = await client.delete(
            f"/api/v1/budgets/{budget_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        response = await client.get(
            f"/api/v1/budgets/{budget_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

        # la secuencia no retrocede
        again = await _create_budget(client, token, customer_id, torta_id)
        assert again["seq"] == "#00002"

    async def test_borrar_no_encontrado_da_404(self, client: AsyncClient):
        token = await _admin_token(client)
        response = await client.delete(
            "/api/v1/budgets/no-existe",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_borrar_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        body = await _create_budget(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.delete(
            f"/api/v1/budgets/{body['id']}",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Listado (RF-P8-06)
# ---------------------------------------------------------------------------


class TestBudgetList:
    async def test_busqueda_por_cliente_y_secuencia(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        jose = await _make_customer(client, token, "José", "3575559999")
        await _create_budget(client, token, customer_id, torta_id)
        await _create_budget(client, token, jose, torta_id)

        body = await _list(client, token)
        assert body["total"] == 2

        assert (await _list(client, token, q="maria"))["total"] == 1
        assert (await _list(client, token, q="MARIA"))["total"] == 1
        assert (await _list(client, token, q="jose"))["total"] == 1
        assert (await _list(client, token, q="0001"))["total"] == 1
        assert (await _list(client, token, q="0002"))["total"] == 1
        assert (await _list(client, token, q="00002"))["total"] == 1
        assert (await _list(client, token, q="#00002"))["total"] == 1
        assert (await _list(client, token, q="zorro"))["total"] == 0

    async def test_filtro_por_estado(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        b1 = await _create_budget(client, token, customer_id, torta_id)
        b2 = await _create_budget(client, token, customer_id, torta_id)
        await client.post(
            f"/api/v1/budgets/{b1['id']}/send",
            headers={"Authorization": f"Bearer {token}"},
        )

        body = await _list(client, token, status="enviado")
        assert body["total"] == 1
        assert body["items"][0]["id"] == b1["id"]

        body = await _list(client, token, status="borrador")
        assert body["total"] == 1

        response = await client.get(
            "/api/v1/budgets",
            params={"status": "vuelto"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_items_del_listado(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        await _create_budget(client, token, customer_id, torta_id, qty=2)
        body = await _list(client, token)
        item = body["items"][0]
        assert item["seq"] == "#00001"
        assert item["customer_name"] == "María"
        assert item["status"] == "borrador"
        assert item["item_count"] == 1
        assert item["total"] == 310000
        assert item["version"] == 0
        assert item["sent_at"] is None

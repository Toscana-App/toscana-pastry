"""Pedidos y clientes (Fase 6, P6): API end-to-end.

Fixture por test: settings (150/h, margen 100%, paso 5, mano de obra
encendida), harina 2.800/kg y torta de limón (250g de harina, 30 min,
6 porciones). Precio base de una torta: 700 (harina) + 75 (mano) = 775;
con margen 100% -> 1.550.
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
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
)
from domain.models import User, UserRole
from domain.orders import InvalidStatusTransitionError, OrderNotEditableError


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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
    app.dependency_overrides[get_customer_repository] = override_get_customer_repository
    app.dependency_overrides[get_order_repository] = override_get_order_repository
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
    client: AsyncClient, token: str, name: str, phone: str
) -> str:
    response = await client.post(
        "/api/v1/customers",
        json={"name": name, "phone": phone},
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


async def _set_stock(
    client: AsyncClient, token: str, ingredient_id: str, delta: str
) -> None:
    response = await client.post(
        f"/api/v1/ingredients/{ingredient_id}/stock",
        json={"delta": delta, "reason": "compra"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def _stock_qty(client: AsyncClient, token: str, ingredient_id: str) -> str:
    response = await client.get(
        f"/api/v1/ingredients/{ingredient_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["ingredient"]["stock_qty"]


async def _movements(
    client: AsyncClient, token: str, ingredient_id: str
) -> list:
    response = await client.get(
        f"/api/v1/ingredients/{ingredient_id}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["items"]


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
    await _set_stock(client, token, flour_id, "10000")
    torta_id = await _make_torta(client, token, flour_id)
    customer_id = await _make_customer(
        client, token, "María", "+357 555-1234"
    )
    return token, flour_id, torta_id, customer_id


async def _create_order(
    client: AsyncClient,
    token: str,
    customer_id: str,
    torta_id: str,
    qty: int = 1,
    portions: int | None = None,
    date: str = "2026-10-20",
    margin_pct: str | None = None,
) -> dict:
    item: dict = {"product_id": torta_id, "qty": qty}
    if portions is not None:
        item["portions"] = portions
    body: dict = {"customer_id": customer_id, "date": date, "items": [item]}
    if margin_pct is not None:
        body["margin_pct"] = margin_pct
    response = await client.post(
        "/api/v1/orders",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Clientes (RF-P6-08)
# ---------------------------------------------------------------------------


class TestCustomers:
    async def test_create_and_list(self, client: AsyncClient):
        token = await _admin_token(client)
        customer_id = await _make_customer(client, token, "María", "+357 555-1234")
        assert customer_id

        response = await client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "María"
        assert body["items"][0]["phone"] == "3575551234"

    async def test_duplicado_devuelve_409_con_id_existente(self, client):
        token = await _admin_token(client)
        first = await _make_customer(client, token, "María", "+357 555-1234")
        response = await client.post(
            "/api/v1/customers",
            # mismo cliente: acentos/case/formato de telefono distintos
            json={"name": "  maria ", "phone": "3575551234"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        assert response.headers.get("X-Customer-Id") == first

    async def test_busqueda_sin_acentos(self, client: AsyncClient):
        token = await _admin_token(client)
        await _make_customer(client, token, "González", "3575550001")
        await _make_customer(client, token, "María", "3575550002")

        response = await client.get(
            "/api/v1/customers",
            params={"q": "gonzalez"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "González"

    async def test_alta_requiere_admin(self, client: AsyncClient):
        token = await _customer_token(client)
        response = await client.post(
            "/api/v1/customers",
            json={"name": "María", "phone": "3575550003"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_leer_lista_permitido_para_cliente(self, client: AsyncClient):
        token = await _customer_token(client)
        response = await client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Crear pedido (RNF-P6-03)
# ---------------------------------------------------------------------------


class TestOrderCreate:
    async def test_crea_con_snapshot_congelado(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)

        assert order["status"] == "nuevo"
        assert order["customer"]["name"] == "María"
        assert order["customer"]["phone"] == "3575551234"
        assert order["date"] == "2026-10-20"
        assert order["margin_pct"] is None
        assert order["total"] == 310000
        assert order["whatsapp_sent_at"] is None

        item = order["items"][0]
        assert item["product_name"] == "Torta de Limón"
        assert item["qty"] == 2
        assert item["portions"] == 6
        assert item["complete"] is True
        assert item["missing_ingredients"] == []
        assert item["price"]["materials"] == 140000
        assert item["price"]["labor"] == 15000
        assert item["price"]["base"] == 155000
        assert item["price"]["margin_pct"] == "100"
        assert item["price"]["final"] == 310000
        assert item["price"]["rounded"] == 310000
        assert item["rounded"] == 310000

        line = item["lines"][0]
        assert line["ingredient_name"] == "Harina"
        assert line["qty"] == "500"  # 250g * 2 unidades
        assert line["unit"] == "g"
        assert line["cost"] == 140000
        assert line["is_missing"] is False

    async def test_porciones_12_doblan_el_precio(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(
            client, token, customer_id, torta_id, qty=1, portions=12
        )
        item = order["items"][0]
        assert item["portions"] == 12
        assert item["price"]["materials"] == 140000
        assert item["price"]["labor"] == 15000
        assert item["rounded"] == 310000
        assert order["total"] == 310000
        assert item["lines"][0]["qty"] == "500"

    async def test_margin_override_reemplaza_al_tenant(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(
            client, token, customer_id, torta_id, qty=1, margin_pct="200"
        )
        assert order["margin_pct"] == "200"
        item = order["items"][0]
        assert item["price"]["margin_pct"] == "200"
        assert item["price"]["base"] == 77500
        assert item["rounded"] == 232500
        assert order["total"] == 232500

    async def test_productos_incompletos_entran_con_desglose_parcial(
        self, client: AsyncClient
    ):
        token, flour_id, torta_id, customer_id = await _setup(client)
        # harina sin precio (0 = sin precio): la torta queda incompleta
        response = await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        item = order["items"][0]
        assert item["complete"] is False
        assert "Harina" in item["missing_ingredients"]
        assert item["lines"][0]["is_missing"] is True
        assert item["lines"][0]["cost"] == 0
        assert item["price"]["materials"] == 0
        # solo mano de obra: 75 base, margen 100% -> 150
        assert item["rounded"] == 15000
        assert order["total"] == 15000

    async def test_cliente_desconocido_da_404(self, client: AsyncClient):
        token, _, torta_id, _ = await _setup(client)
        response = await client.post(
            "/api/v1/orders",
            json={
                "customer_id": "no-existe",
                "date": "2026-10-20",
                "items": [{"product_id": torta_id, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    async def test_producto_desconocido_da_400(self, client: AsyncClient):
        token, _, _, customer_id = await _setup(client)
        response = await client.post(
            "/api/v1/orders",
            json={
                "customer_id": customer_id,
                "date": "2026-10-20",
                "items": [{"product_id": "no-existe", "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_preview_no_persiste(self, client: AsyncClient):
        token, _, torta_id, _ = await _setup(client)
        response = await client.post(
            "/api/v1/orders/preview",
            json={"items": [{"product_id": torta_id, "qty": 2}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["margin_pct"] == "100"
        assert body["tenant_margin_pct"] == "100"
        assert body["total"] == 310000
        assert body["items"][0]["rounded"] == 310000

        listing = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listing.json()["total"] == 0

    async def test_preview_con_margin_override(self, client: AsyncClient):
        token, _, torta_id, _ = await _setup(client)
        response = await client.post(
            "/api/v1/orders/preview",
            json={
                "margin_pct": "200",
                "items": [{"product_id": torta_id, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["margin_pct"] == "200"
        assert body["tenant_margin_pct"] == "100"
        assert body["total"] == 232500

    async def test_crear_requiere_admin(self, client: AsyncClient):
        _, _, torta_id, _ = await _setup(client)
        token = await _customer_token(client)
        response = await client.post(
            "/api/v1/orders",
            json={
                "customer_id": "x",
                "date": "2026-10-20",
                "items": [{"product_id": torta_id, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_snapshot_sobrevive_a_cambios_de_catalogo(
        self, client: AsyncClient
    ):
        """RNF-P6-03: el desglose congelado no se recalcula."""
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        order_id = order["id"]

        # el catalogo cambia: sube el precio de la harina y la receta
        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 999900},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.patch(
            f"/api/v1/products/{torta_id}",
            json={"recipe": [{"ingredient_id": flour_id, "qty": "999", "unit": "g"}]},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 155000
        assert body["items"][0]["lines"][0]["qty"] == "250"
        assert body["items"][0]["lines"][0]["cost"] == 70000


# ---------------------------------------------------------------------------
# Maquina de estados + stock (RNF-P6-01/02/04)
# ---------------------------------------------------------------------------


class TestOrderStatus:
    async def test_flujo_completo_con_descuento_y_movimiento(self, client):
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)
        order_id = order["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmado"
        # 10000g - 500g (2 tortas x 250g)
        assert await _stock_qty(client, token, flour_id) == "9500"
        reasons = [m["reason"] for m in await _movements(client, token, flour_id)]
        assert "pedido" in reasons

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "entregado"

    async def test_stock_insuficiente_da_409_y_no_descuenta(
        self, client: AsyncClient
    ):
        token, flour_id, torta_id, customer_id = await _setup(client)
        # deja solo 400g en stock
        await _set_stock(client, token, flour_id, "-9600")
        order = await _create_order(
            client, token, customer_id, torta_id, qty=1, portions=12
        )  # pide 500g
        order_id = order["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["error"] == "Stock insuficiente para confirmar el pedido"
        assert len(body["insufficient_stock"]) == 1
        assert body["insufficient_stock"][0]["ingredient_name"] == "Harina"
        assert body["insufficient_stock"][0]["available"] == "400"
        assert body["insufficient_stock"][0]["required"] == "500"

        # nada cambio: el pedido sigue nuevo y el stock intacto
        detail = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["status"] == "nuevo"
        assert await _stock_qty(client, token, flour_id) == "400"

    async def test_cancelar_desde_confirmado_repone_stock(self, client):
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)
        order_id = order["id"]
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert await _stock_qty(client, token, flour_id) == "9500"

        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "cancelado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelado"
        assert await _stock_qty(client, token, flour_id) == "10000"
        reasons = [m["reason"] for m in await _movements(client, token, flour_id)]
        assert "anulacion" in reasons

    async def test_segundo_confirm_con_orden_vieja_es_rechazado(
        self, client: AsyncClient, db_session
    ):
        """Repo-level: dos confirm sobre el mismo Order leido antes (lo que
        pasa con dos PATCH concurrentes). SQLite no soporta FOR UPDATE, asi
        que se prueba la revalidacion de estado secuencialmente."""
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)
        repo = SQLOrderRepository(db_session)
        stale = await repo.get_full(order["id"])

        confirmed = await repo.confirm(stale)
        assert confirmed.status == "confirmado"
        with pytest.raises(InvalidStatusTransitionError):
            await repo.confirm(stale)

        assert await _stock_qty(client, token, flour_id) == "9500"
        movements = await _movements(client, token, flour_id)
        assert [m["reason"] for m in movements].count("pedido") == 1

    async def test_segundo_cancel_con_orden_vieja_es_rechazado(
        self, client: AsyncClient, db_session
    ):
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)
        repo = SQLOrderRepository(db_session)
        confirmed = await repo.confirm(await repo.get_full(order["id"]))

        await repo.cancel(confirmed)
        with pytest.raises(InvalidStatusTransitionError):
            await repo.cancel(confirmed)
        with pytest.raises(InvalidStatusTransitionError):
            await repo.mark_delivered(confirmed)

        assert await _stock_qty(client, token, flour_id) == "10000"
        movements = await _movements(client, token, flour_id)
        assert [m["reason"] for m in movements].count("anulacion") == 1

    async def test_update_sobre_pedido_confirmado_es_rechazado(
        self, client: AsyncClient, db_session
    ):
        token, flour_id, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=2)
        repo = SQLOrderRepository(db_session)
        stale = await repo.get_full(order["id"])
        await repo.confirm(stale)

        with pytest.raises(OrderNotEditableError):
            await repo.update_full(stale)

    async def test_incompleto_no_desuenta_stock(self, client: AsyncClient):
        token, flour_id, torta_id, customer_id = await _setup(client)
        await client.patch(
            f"/api/v1/ingredients/{flour_id}",
            json={"price_per_unit": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        order_id = order["id"]
        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        # sin lineas con precio: nada que descontar
        assert await _stock_qty(client, token, flour_id) == "10000"

    async def test_transiciones_invalidas_da_400(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id)
        order_id = order["id"]

        # nuevo no puede ir directo a entregado
        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

        # nuevo tampoco se cancela (no hay stock descuenta que reponer)
        response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "cancelado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

        # estados finales no avanzan
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        for target in ("nuevo", "confirmado", "entregado", "cancelado"):
            response = await client.patch(
                f"/api/v1/orders/{order_id}/status",
                json={"status": target},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 400

    async def test_editar_solo_estado_nuevo(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id)
        order_id = order["id"]
        await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"date": "2026-10-25"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_editar_items_reccongela_snapshots(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        order_id = order["id"]
        assert order["total"] == 155000

        response = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"items": [{"product_id": torta_id, "qty": 2}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 310000
        assert body["items"][0]["qty"] == 2
        assert body["items"][0]["lines"][0]["qty"] == "500"

    async def test_editar_margin_recongela_con_items_existentes(
        self, client: AsyncClient
    ):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        order_id = order["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"margin_pct": "200"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["margin_pct"] == "200"
        assert body["items"][0]["price"]["margin_pct"] == "200"
        assert body["total"] == 232500

    async def test_cambiar_cliente_en_edicion(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        otro = await _make_customer(client, token, "José", "3575559999")
        order = await _create_order(client, token, customer_id, torta_id)
        order_id = order["id"]

        response = await client.patch(
            f"/api/v1/orders/{order_id}",
            json={"customer_id": otro},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["customer"]["name"] == "José"


# ---------------------------------------------------------------------------
# Filtros (RF-P6-05)
# ---------------------------------------------------------------------------


class TestOrderFilters:
    async def test_filtro_por_estado_cliente_y_fechas(self, client):
        token, _, torta_id, customer_id = await _setup(client)
        jorge = await _make_customer(client, token, "Jorge", "3575557777")

        o1 = await _create_order(
            client, token, customer_id, torta_id, date="2026-10-01"
        )
        o2 = await _create_order(
            client, token, jorge, torta_id, date="2026-10-15"
        )
        await client.patch(
            f"/api/v1/orders/{o2['id']}/status",
            json={"status": "confirmado"},
            headers={"Authorization": f"Bearer {token}"},
        )

        async def _list(**params):
            response = await client.get(
                "/api/v1/orders",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            return response.json()

        assert (await _list())["total"] == 2
        assert (await _list(status="confirmado"))["total"] == 1
        assert (await _list(status="nuevo"))["total"] == 1
        assert (await _list(customer_id=jorge))["total"] == 1
        assert (await _list(q="jorge"))["total"] == 1
        assert (await _list(q="JORG"))["total"] == 1  # case-insensitive
        assert (await _list(q="zorg"))["total"] == 0
        assert (
            await _list(date_from="2026-10-10", date_to="2026-10-31")
        )["total"] == 1
        assert (await _list(date_from="2026-10-01", date_to="2026-10-31"))["total"] == 2
        assert (await _list(date_from="2026-11-01"))["total"] == 0
        # estado invalido -> 422 (pattern del query)
        response = await client.get(
            "/api/v1/orders",
            params={"status": "vuelto"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# WhatsApp (RF-P6-06)
# ---------------------------------------------------------------------------


class TestWhatsApp:
    async def test_link_wa_me_y_auditoria(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id, qty=1)
        order_id = order["id"]

        response = await client.post(
            f"/api/v1/orders/{order_id}/whatsapp-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["url"].startswith("https://wa.me/3575551234?text=")
        assert "Hola María:" in body["message"]
        assert "Torta de Limón" in body["message"]
        assert "$1.550" in body["message"]

        detail = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.json()["whatsapp_sent_at"]

    async def test_link_requiere_admin(self, client: AsyncClient):
        token, _, torta_id, customer_id = await _setup(client)
        order = await _create_order(client, token, customer_id, torta_id)
        customer_token = await _customer_token(client)
        response = await client.post(
            f"/api/v1/orders/{order['id']}/whatsapp-link",
            headers={"Authorization": f"Bearer {customer_token}"},
        )
        assert response.status_code == 403

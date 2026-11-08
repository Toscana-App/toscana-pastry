import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from main import app
from data.accent import accent_fold
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from domain.models import User, UserRole


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    app.dependency_overrides[get_product_repository] = override_get_product_repository
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


async def _set_settings(client: AsyncClient, headers) -> None:
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
            "urgent_surcharge_pct": "20",
            "default_prep_minutes": 30,
            "default_servings": 6,
            "default_difficulty": "simple",
        },
        headers=headers,
    )
    assert response.status_code == 200


async def _create_ingredient(
    client: AsyncClient, headers, name, unit="kg", price=280000
):
    response = await client.post(
        "/api/v1/ingredients",
        json={
            "name": name,
            "unit": unit,
            "price_per_unit": price,
            "stock_qty": 0,
            "low_stock_threshold": 0,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_product(
    client: AsyncClient,
    headers,
    name="Torta de Almendra",
    category="Tortas",
    recipe=None,
    **extra,
):
    payload = {
        "name": name,
        "category": category,
        "recipe": recipe
        or [{"ingredient_id": "flour", "qty": 250, "unit": "g"}],
    }
    payload.update(extra)
    response = await client.post("/api/v1/products", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _seed_published(client: AsyncClient):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina de Almendra")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    return headers, product


# --- Default: nace oculto ---------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_hidden_by_default(client):
    headers, product = await _seed_published(client)
    assert product["available"] is False
    assert product["image_url"] is None
    detail = await client.get(
        f"/api/v1/products/{product['id']}", headers=headers
    )
    assert detail.status_code == 200
    assert detail.json()["available"] is False
    assert detail.json()["image_url"] is None
    listing = (
        await client.get("/api/v1/products", headers=headers)
    ).json()
    item = next(i for i in listing["items"] if i["id"] == product["id"])
    assert item["available"] is False
    assert item["image_url"] is None


# --- Publicar / retirar ------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_publish_complete_product(client):
    headers, product = await _seed_published(client)
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["available"] is True
    detail = await client.get(
        f"/api/v1/products/{product['id']}", headers=headers
    )
    assert detail.json()["available"] is True


@pytest.mark.asyncio
async def test_patch_unpublish(client):
    headers, product = await _seed_published(client)
    await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": True},
        headers=headers,
    )
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": False},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["available"] is False


@pytest.mark.asyncio
async def test_partial_update_preserves_availability(client):
    headers, product = await _seed_published(client)
    await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": True},
        headers=headers,
    )
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"description": "Sin gluten"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["description"] == "Sin gluten"


# --- 409 publicar incompleto --------------------------------------------------


@pytest.mark.asyncio
async def test_publish_incomplete_product_is_409(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    sin_precio = await _create_ingredient(
        client, headers, "Azucar Sin Precio", price=0
    )
    product = await _create_product(
        client,
        headers,
        name="Incompleto",
        recipe=[{"ingredient_id": sin_precio["id"], "qty": 100, "unit": "g"}],
    )
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": True},
        headers=headers,
    )
    assert response.status_code == 409
    body = response.json()
    assert body["missing_ingredients"] == ["Azucar Sin Precio"]
    detail = await client.get(
        f"/api/v1/products/{product['id']}", headers=headers
    )
    assert detail.json()["available"] is False


@pytest.mark.asyncio
async def test_publish_nonexistent_is_404(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await client.patch(
        "/api/v1/products/no-existe",
        json={"available": True},
        headers=headers,
    )
    assert response.status_code == 404


# --- RBAC ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_forbidden_for_customer(client):
    headers, product = await _seed_published(client)
    customer_headers = {
        "Authorization": f"Bearer {await _customer_token(client)}"
    }
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"available": True},
        headers=customer_headers,
    )
    assert response.status_code == 403


# --- Migracion -----------------------------------------------------------------


def test_migration_0009_adds_available_and_image_url():
    path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "migrations", "0009_products_available_image.sql",
    )
    with open(os.path.normpath(path), encoding="utf-8") as f:
        sql = f.read()
    assert "ALTER TABLE products ADD COLUMN available" in sql
    assert "ADD COLUMN image_url" in sql

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
from data.db import get_db
from data.models import Base
from data.accent import accent_fold
from data.repositories.calc.sql_calc_default_cost_repository import (
    SQLCalcDefaultCostRepository,
)
from data.repositories.calc.sql_calc_material_category_repository import (
    SQLCalcMaterialCategoryRepository,
)
from data.repositories.calc.sql_calc_material_repository import (
    SQLCalcMaterialRepository,
)
from data.repositories.calc.sql_calc_product_category_repository import (
    SQLCalcProductCategoryRepository,
)
from data.repositories.calc.sql_calc_product_repository import (
    SQLCalcProductRepository,
)
from data.repositories.calc.sql_calc_settings_repository import (
    SQLCalcSettingsRepository,
)
from data.repositories.calc.sql_calc_supplier_repository import (
    SQLCalcSupplierRepository,
)
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
from api.v1.products.dependencies import (
    get_product_repository as get_product_repository_products,
)
from api.v1.orders.dependencies import (
    get_customer_repository,
    get_order_repository,
    get_product_repository as get_product_repository_orders,
)
from api.v1.budgets.dependencies import get_budget_repository
from api.v1.pdf.dependencies import get_document_repository
from api.v1.calc.dependencies import (
    get_calc_default_cost_repository,
    get_calc_material_category_repository,
    get_calc_material_repository,
    get_calc_product_category_repository,
    get_calc_product_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
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

    async def override_get_product_repository_products():
        yield SQLProductRepository(db_session)

    async def override_get_product_repository_orders():
        yield SQLProductRepository(db_session)

    async def override_get_customer_repository():
        yield SQLCustomerRepository(db_session)

    async def override_get_order_repository():
        yield SQLOrderRepository(db_session)

    async def override_get_budget_repository():
        yield SQLBudgetRepository(db_session)

    async def override_get_document_repository():
        yield SQLDocumentRepository(db_session)

    async def override_get_calc_settings_repository():
        yield SQLCalcSettingsRepository(db_session)

    async def override_get_calc_material_category_repository():
        yield SQLCalcMaterialCategoryRepository(db_session)

    async def override_get_calc_product_category_repository():
        yield SQLCalcProductCategoryRepository(db_session)

    async def override_get_calc_supplier_repository():
        yield SQLCalcSupplierRepository(db_session)

    async def override_get_calc_default_cost_repository():
        yield SQLCalcDefaultCostRepository(db_session)

    async def override_get_calc_material_repository():
        yield SQLCalcMaterialRepository(db_session)

    async def override_get_calc_product_repository():
        yield SQLCalcProductRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = (
        override_get_settings_repository
    )
    app.dependency_overrides[get_ingredient_repository] = (
        override_get_ingredient_repository
    )
    app.dependency_overrides[get_product_repository_products] = (
        override_get_product_repository_products
    )
    app.dependency_overrides[get_product_repository_orders] = (
        override_get_product_repository_orders
    )
    app.dependency_overrides[get_customer_repository] = (
        override_get_customer_repository
    )
    app.dependency_overrides[get_order_repository] = override_get_order_repository
    app.dependency_overrides[get_budget_repository] = override_get_budget_repository
    app.dependency_overrides[get_document_repository] = (
        override_get_document_repository
    )
    app.dependency_overrides[get_calc_settings_repository] = (
        override_get_calc_settings_repository
    )
    app.dependency_overrides[get_calc_material_category_repository] = (
        override_get_calc_material_category_repository
    )
    app.dependency_overrides[get_calc_product_category_repository] = (
        override_get_calc_product_category_repository
    )
    app.dependency_overrides[get_calc_supplier_repository] = (
        override_get_calc_supplier_repository
    )
    app.dependency_overrides[get_calc_default_cost_repository] = (
        override_get_calc_default_cost_repository
    )
    app.dependency_overrides[get_calc_material_repository] = (
        override_get_calc_material_repository
    )
    app.dependency_overrides[get_calc_product_repository] = (
        override_get_calc_product_repository
    )

    user_repo = SQLUserRepository(db_session)
    await user_repo.save(User(email="admin@example.com", role=UserRole.ADMIN))
    await user_repo.save(User(email="negocio@example.com", role=UserRole.NEGOCIO))
    await user_repo.save(User(email="customer@example.com", role=UserRole.CUSTOMER))

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed(client: AsyncClient) -> dict:
    token = await _token_for(client, "admin@example.com")
    headers = _auth(token)
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
        headers=headers,
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/v1/ingredients",
        json={
            "name": "Harina",
            "unit": "kg",
            "price_per_unit": 280000,
            "stock_qty": 100,
            "low_stock_threshold": 0,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    ingredient_id = response.json()["id"]
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta de Limon",
            "category": "Tortas",
            "description": "Torta clasica",
            "recipe": [
                {"ingredient_id": ingredient_id, "qty": "250", "unit": "g"}
            ],
            "prep_time_min": 30,
            "servings": 6,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    product_id = response.json()["id"]
    response = await client.post(
        "/api/v1/customers",
        json={"name": "Maria", "phone": "+357 555-1234"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    customer_id = response.json()["id"]
    response = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "date": "2026-10-20",
            "items": [{"product_id": product_id, "qty": 1}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["id"]
    response = await client.post(
        "/api/v1/budgets",
        json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "qty": 1}],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    budget_id = response.json()["id"]
    response = await client.post(
        "/api/v1/calc/materials", json={"name": "Mantequilla"}, headers=headers
    )
    assert response.status_code == 201, response.text
    calc_material_id = response.json()["id"]
    response = await client.post(
        "/api/v1/calc/products", json={"name": "Brownie"}, headers=headers
    )
    assert response.status_code == 201, response.text
    calc_product_id = response.json()["id"]
    return {
        "ingredient_id": ingredient_id,
        "product_id": product_id,
        "customer_id": customer_id,
        "order_id": order_id,
        "budget_id": budget_id,
        "calc_material_id": calc_material_id,
        "calc_product_id": calc_product_id,
    }


@pytest_asyncio.fixture
async def seeded(client: AsyncClient) -> dict:
    return await _seed(client)


MANAGEMENT_ENDPOINTS = [
    "/api/v1/ingredients",
    "/api/v1/ingredients/{ingredient_id}",
    "/api/v1/ingredients/{ingredient_id}/movements",
    "/api/v1/customers",
    "/api/v1/customers/{customer_id}",
    "/api/v1/budgets",
    "/api/v1/budgets/{budget_id}",
    "/api/v1/orders",
    "/api/v1/orders/{order_id}",
    "/api/v1/tenant/settings",
    "/api/v1/pdf/budgets/{budget_id}/pdf",
    "/api/v1/products",
    "/api/v1/products/{product_id}",
    "/api/v1/calc/settings",
    "/api/v1/calc/material-categories",
    "/api/v1/calc/product-categories",
    "/api/v1/calc/suppliers",
    "/api/v1/calc/default-costs",
    "/api/v1/calc/materials",
    "/api/v1/calc/materials/{calc_material_id}",
    "/api/v1/calc/materials/{calc_material_id}/cost-history",
    "/api/v1/calc/products",
    "/api/v1/calc/products/price-list",
    "/api/v1/calc/products/price-list/export",
    "/api/v1/calc/products/{calc_product_id}",
    "/api/v1/calc/products/{calc_product_id}/versions",
    "/api/v1/calc/dashboard",
]


@pytest.mark.parametrize("path", MANAGEMENT_ENDPOINTS)
async def test_customer_forbidden_on_management_endpoints(
    path: str, client: AsyncClient, seeded: dict
):
    token = await _token_for(client, "customer@example.com")
    response = await client.get(path.format(**seeded), headers=_auth(token))
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("path", MANAGEMENT_ENDPOINTS)
async def test_negocio_forbidden_on_management_endpoints(
    path: str, client: AsyncClient, seeded: dict
):
    token = await _token_for(client, "negocio@example.com")
    response = await client.get(path.format(**seeded), headers=_auth(token))
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.parametrize("path", MANAGEMENT_ENDPOINTS)
async def test_admin_allowed_on_management_endpoints(
    path: str, client: AsyncClient, seeded: dict
):
    token = await _token_for(client, "admin@example.com")
    response = await client.get(path.format(**seeded), headers=_auth(token))
    assert response.status_code in (200, 204), (
        f"{path} -> {response.status_code}: {response.text[:200]}"
    )


async def test_anonymous_forbidden_on_management_endpoints(client: AsyncClient):
    for path in (
        "/api/v1/ingredients",
        "/api/v1/tenant/settings",
        "/api/v1/calc/dashboard",
    ):
        response = await client.get(path)
        assert response.status_code == 401, f"{path} -> {response.status_code}"


async def test_customer_portal_audience_still_allowed(
    client: AsyncClient, seeded: dict
):
    token = await _token_for(client, "customer@example.com")
    response = await client.get(
        "/api/v1/products?audience=consumidor_final", headers=_auth(token)
    )
    assert response.status_code == 200, response.text


async def test_negocio_portal_audience_still_allowed(
    client: AsyncClient, seeded: dict
):
    token = await _token_for(client, "negocio@example.com")
    response = await client.get(
        "/api/v1/products?audience=revendedores", headers=_auth(token)
    )
    assert response.status_code == 200, response.text

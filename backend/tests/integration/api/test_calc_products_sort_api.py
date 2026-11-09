
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.calc.dependencies import (
    get_calc_material_category_repository,
    get_calc_material_repository,
    get_calc_product_category_repository,
    get_calc_product_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
from data.db import get_db
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
from domain.models import User, UserRole
from main import app



@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_calc_settings_repository():
        yield SQLCalcSettingsRepository(db_session)

    async def override_get_material_category_repo():
        yield SQLCalcMaterialCategoryRepository(db_session)

    async def override_get_product_category_repo():
        yield SQLCalcProductCategoryRepository(db_session)

    async def override_get_supplier_repo():
        yield SQLCalcSupplierRepository(db_session)

    async def override_get_material_repo():
        yield SQLCalcMaterialRepository(db_session)

    async def override_get_product_repo():
        yield SQLCalcProductRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_calc_settings_repository] = (
        override_get_calc_settings_repository
    )
    app.dependency_overrides[get_calc_material_category_repository] = (
        override_get_material_category_repo
    )
    app.dependency_overrides[get_calc_product_category_repository] = (
        override_get_product_category_repo
    )
    app.dependency_overrides[get_calc_supplier_repository] = override_get_supplier_repo
    app.dependency_overrides[get_calc_material_repository] = override_get_material_repo
    app.dependency_overrides[get_calc_product_repository] = override_get_product_repo

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




async def _admin(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_material(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Mantequilla"}
    payload.update(overrides)
    response = await client.post(
        "/api/v1/calc/materials", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_product(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Brownie"}
    payload.update(overrides)
    response = await client.post(
        "/api/v1/calc/products", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_product_category(
    client: AsyncClient, token: str, name: str = "Postres"
) -> dict:
    response = await client.post(
        "/api/v1/calc/product-categories", json={"name": name}, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _seed_sort_products(client: AsyncClient, token: str) -> dict:
    material = await _create_material(
        client, token,
        unit_of_measure="kg",
        purchase_total_price=10000, package_quantity="1",
    )
    lines = [{"material_id": material["id"], "quantity_used": "1"}]
    alpha = await _create_product(
        client, token, name="Alpha", margin_percent="50", materials=lines
    )
    beta = await _create_product(
        client, token, name="Beta", margin_percent="30", materials=lines
    )
    gamma = await _create_product(
        client, token, name="Gamma", margin_percent="10", materials=lines
    )
    return {
        "alpha": alpha["product"]["id"],
        "beta": beta["product"]["id"],
        "gamma": gamma["product"]["id"],
    }


async def _names(client: AsyncClient, token: str, **params) -> list:
    response = await client.get(
        "/api/v1/calc/products",
        params={k: str(v) for k, v in params.items()},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["items"]]




class TestSortParam:
    async def test_invalid_sort_returns_422(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/products", params={"sort": "bogus"}, headers=_auth(token)
        )
        assert response.status_code == 422

    async def test_invalid_dir_returns_422(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/products", params={"dir": "sideways"}, headers=_auth(token)
        )
        assert response.status_code == 422

    async def test_default_sort_is_name_asc(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        assert await _names(client, token) == ["Alpha", "Beta", "Gamma"]

    async def test_sort_name_desc(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        assert await _names(client, token, sort="name", dir="desc") == [
            "Gamma",
            "Beta",
            "Alpha",
        ]

    async def test_sort_price_desc_uses_engine_values(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        assert await _names(client, token, sort="price", dir="desc") == [
            "Alpha",
            "Beta",
            "Gamma",
        ]
        assert await _names(client, token, sort="price", dir="asc") == [
            "Gamma",
            "Beta",
            "Alpha",
        ]

    async def test_sort_price_follows_settings_rounding(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        payload = {
            "business_name": "Toscana Pastry",
            "main_currency_name": "Peso",
            "main_currency_symbol": "$",
            "default_margin_percent": "30",
            "default_discount_percent": "0",
            "default_tax_percent": "19",
            "rounding_mode": "commercial_99",
        }
        response = await client.put(
            "/api/v1/calc/settings", json=payload, headers=_auth(token)
        )
        assert response.status_code == 200, response.text
        assert await _names(client, token, sort="price", dir="desc") == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    async def test_sort_cost_desc_ties_by_name_asc(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        assert await _names(client, token, sort="cost", dir="desc") == [
            "Alpha",
            "Beta",
            "Gamma",
        ]
        assert await _names(client, token, sort="cost", dir="asc") == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    async def test_sort_margin_uses_stored_percent(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        assert await _names(client, token, sort="margin", dir="asc") == [
            "Gamma",
            "Beta",
            "Alpha",
        ]
        assert await _names(client, token, sort="margin", dir="desc") == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    async def test_sort_excludes_deleted(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        deleted = await _create_product(client, token, name="ZZZ")
        await client.delete(
            f"/api/v1/calc/products/{deleted['product']['id']}", headers=_auth(token)
        )
        names = await _names(client, token, sort="price", dir="desc")
        assert "ZZZ" not in names
        assert set(names) == {"Alpha", "Beta", "Gamma"}

    async def test_python_side_pagination_with_sort(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        page1 = await client.get(
            "/api/v1/calc/products",
            params={"sort": "price", "dir": "desc", "page": 1, "page_size": 2},
            headers=_auth(token),
        )
        page2 = await client.get(
            "/api/v1/calc/products",
            params={"sort": "price", "dir": "desc", "page": 2, "page_size": 2},
            headers=_auth(token),
        )
        assert page1.status_code == 200
        body1 = page1.json()
        assert body1["total"] == 3
        assert [item["name"] for item in body1["items"]] == ["Alpha", "Beta"]
        body2 = page2.json()
        assert [item["name"] for item in body2["items"]] == ["Gamma"]

    async def test_sort_name_paginates_with_costs_for_page(self, client):
        token = await _admin(client)
        await _seed_sort_products(client, token)
        for direction, p1, p2 in (
            ("asc", ["Alpha", "Beta"], ["Gamma"]),
            ("desc", ["Gamma", "Beta"], ["Alpha"]),
        ):
            bodies = []
            for page in (1, 2):
                response = await client.get(
                    "/api/v1/calc/products",
                    params={
                        "sort": "name",
                        "dir": direction,
                        "page": page,
                        "page_size": 2,
                    },
                    headers=_auth(token),
                )
                assert response.status_code == 200, response.text
                bodies.append(response.json())
            assert [i["name"] for i in bodies[0]["items"]] == p1
            assert [i["name"] for i in bodies[1]["items"]] == p2
            assert bodies[0]["total"] == bodies[1]["total"] == 3




class TestEnrichedItem:
    async def test_item_fields_and_computed_costs(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token, name="Postres")
        material = await _create_material(
            client, token,
            unit_of_measure="kg",
            purchase_total_price=10000, package_quantity="1",
        )
        await _create_product(
            client,
            token,
            name="Alpha",
            sku="AL-1",
            status="active",
            category_id=cat["id"],
            margin_percent="50",
            materials=[{"material_id": material["id"], "quantity_used": "1"}],
        )
        response = await client.get(
            "/api/v1/calc/products", headers=_auth(token)
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert set(item.keys()) == {
            "id",
            "name",
            "sku",
            "category_name",
            "status",
            "product_total_cost",
            "final_sale_price",
            "margin_percent",
            "last_recalculated_at",
        }
        assert item["name"] == "Alpha"
        assert item["sku"] == "AL-1"
        assert item["category_name"] == "Postres"
        assert item["status"] == "active"
        assert item["product_total_cost"] == 10000
        assert item["final_sale_price"] == 23800
        assert float(item["margin_percent"]) == 50.0
        assert item["last_recalculated_at"] is None

    async def test_item_without_category_has_null_category_name(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="SinCategoria")
        response = await client.get(
            "/api/v1/calc/products", headers=_auth(token)
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["category_name"] is None

    async def test_filters_and_search_still_work_with_sort(self, client):
        token = await _admin(client)
        seed = await _seed_sort_products(client, token)
        await client.patch(
            f"/api/v1/calc/products/{seed['gamma']}",
            json={"sku": "TORTA-9"},
            headers=_auth(token),
        )
        response = await client.get(
            "/api/v1/calc/products",
            params={"q": "torta", "sort": "price"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Gamma"

        response = await client.get(
            "/api/v1/calc/products",
            params={"q": "bet", "status": "active"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

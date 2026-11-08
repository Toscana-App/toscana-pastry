"""Integration tests for GET /calc/dashboard (RF-P3CC-05).

Covers: exact counts (materials by persisted derived status, products
by status excluding deleted; archived not in the response), averages
over the 3 active products quantized to cents, `top_by_price` /
`bottom_by_margin` (<=5, ordering, item shape), truncation past 5
actives, the empty state, and auth (401, D2).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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

# ─── Fixtures ───────────────────────────────────────────────────────────


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


# ─── Helpers ────────────────────────────────────────────────────────────


async def _admin(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com"}
    )
    assert response.status_code == 200
    return response.cookies["auth_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_material(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Materiales"}
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


async def _seed_dashboard(client: AsyncClient, token: str) -> None:
    """2 materiales activos + 2 incomplete; 3 activos (qty 1/2/3 x
    100.00, margen 50/30/10) + 1 draft + 1 archived + 1 eliminado.

    Valores esperados (motor: discount 0, tax 19, rounding none),
    calculados a mano:
      Alpha: cost 100.00, final 238.00 (m50)
      Beta:  cost 200.00, final 339.99 (m30)
      Gamma: cost 300.00, final 396.66 (m10)
    Promedios: cost 200.00, final (238.00+339.99+396.66)/3 = 324.88.
    """
    await _create_material(
        client, token, name="Mantequilla",
        purchase_total_price=10000, package_quantity="1",
    )
    await _create_material(
        client, token, name="Harina",
        purchase_total_price=5000, package_quantity="1",
    )
    await _create_material(client, token, name="Azucar")  # incomplete
    await _create_material(client, token, name="Huevo")  # incomplete
    material = (
        await client.get(
            "/api/v1/calc/materials",
            params={"q": "Mantequilla"},
            headers=_auth(token),
        )
    ).json()["items"][0]
    lines = [{"material_id": material["id"]}]
    await _create_product(
        client,
        token,
        name="Alpha",
        status="active",
        margin_percent="50",
        materials=[{**lines[0], "quantity_used": "1"}],
    )
    await _create_product(
        client,
        token,
        name="Beta",
        status="active",
        margin_percent="30",
        materials=[{**lines[0], "quantity_used": "2"}],
    )
    await _create_product(
        client,
        token,
        name="Gamma",
        status="active",
        margin_percent="10",
        materials=[{**lines[0], "quantity_used": "3"}],
    )
    await _create_product(
        client,
        token,
        name="Delta",
        status="draft",
        materials=[{**lines[0], "quantity_used": "1"}],
    )
    await _create_product(
        client,
        token,
        name="Epsilon",
        status="archived",
        materials=[{**lines[0], "quantity_used": "1"}],
    )
    zeta = await _create_product(
        client,
        token,
        name="Zeta",
        status="active",
        materials=[{**lines[0], "quantity_used": "1"}],
    )
    await client.delete(
        f"/api/v1/calc/products/{zeta['product']['id']}", headers=_auth(token)
    )


async def _dashboard(client: AsyncClient, token: str) -> dict:
    response = await client.get("/api/v1/calc/dashboard", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


# ─── Dashboard (RF-P3CC-05) ────────────────────────────────────────────


class TestDashboard:
    async def test_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/dashboard")
        assert response.status_code == 401

    async def test_counts_averages_and_exact_shape(self, client):
        token = await _admin(client)
        await _seed_dashboard(client, token)
        body = await _dashboard(client, token)
        assert set(body.keys()) == {
            "active_materials",
            "active_products",
            "draft_products",
            "incomplete_materials",
            "avg_product_cost",
            "avg_final_price",
            "top_by_price",
            "bottom_by_margin",
        }
        assert body["active_materials"] == 2
        assert body["incomplete_materials"] == 2
        assert body["active_products"] == 3  # el eliminado no cuenta
        assert body["draft_products"] == 1
        # archived NO va en la respuesta (no hay ese campo).
        assert body["avg_product_cost"] == 20000
        assert body["avg_final_price"] == 32488

    async def test_top_by_price_desc(self, client):
        token = await _admin(client)
        await _seed_dashboard(client, token)
        body = await _dashboard(client, token)
        top = body["top_by_price"]
        assert [item["name"] for item in top] == ["Gamma", "Beta", "Alpha"]
        assert top[0]["final_sale_price"] == 39666
        assert float(top[0]["margin_percent"]) == 10.0
        assert set(top[0].keys()) == {
            "id",
            "name",
            "final_sale_price",
            "margin_percent",
        }
        assert top[2]["final_sale_price"] == 23800

    async def test_bottom_by_margin_asc(self, client):
        token = await _admin(client)
        await _seed_dashboard(client, token)
        body = await _dashboard(client, token)
        bottom = body["bottom_by_margin"]
        assert [item["name"] for item in bottom] == ["Gamma", "Beta", "Alpha"]
        assert bottom[0]["product_total_cost"] == 30000
        assert float(bottom[0]["margin_percent"]) == 10.0
        assert set(bottom[0].keys()) == {
            "id",
            "name",
            "product_total_cost",
            "margin_percent",
        }
        assert bottom[2]["product_total_cost"] == 10000

    async def test_truncates_at_five_with_more_actives(self, client):
        token = await _admin(client)
        material = await _create_material(
            client, token, name="Base",
            purchase_total_price=10000, package_quantity="1",
        )
        for index in range(6):
            await _create_product(
                client,
                token,
                name=f"P{index}",
                status="active",
                margin_percent=str(index),
                materials=[
                    {"material_id": material["id"], "quantity_used": str(index + 1)}
                ],
            )
        body = await _dashboard(client, token)
        assert len(body["top_by_price"]) == 5
        assert len(body["bottom_by_margin"]) == 5
        # bottom por margen asc: P0..P4.
        assert [item["name"] for item in body["bottom_by_margin"]] == [
            "P0",
            "P1",
            "P2",
            "P3",
            "P4",
        ]

    async def test_empty_state(self, client):
        token = await _admin(client)
        body = await _dashboard(client, token)
        assert body == {
            "active_materials": 0,
            "active_products": 0,
            "draft_products": 0,
            "incomplete_materials": 0,
            "avg_product_cost": 0,
            "avg_final_price": 0,
            "top_by_price": [],
            "bottom_by_margin": [],
        }

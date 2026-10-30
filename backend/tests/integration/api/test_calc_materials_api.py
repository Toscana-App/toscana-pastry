"""Integration tests for the Calc Materials API (RF-P2CC-01..05).

Covers auth (401/403), CRUD, derived unit_cost/status (never from
client), append-only cost history, FK validation (404), delete-in-use
(409) and search + pagination on /calc/materials (S4, S3).
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.calc.dependencies import (
    get_calc_default_cost_repository,
    get_calc_material_category_repository,
    get_calc_material_repository,
    get_calc_product_category_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
from data.accent import accent_fold
from data.db import get_db
from data.models import Base
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

    async def override_get_default_cost_repo():
        yield SQLCalcDefaultCostRepository(db_session)

    async def override_get_material_repo():
        yield SQLCalcMaterialRepository(db_session)

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
    app.dependency_overrides[get_calc_default_cost_repository] = (
        override_get_default_cost_repo
    )
    app.dependency_overrides[get_calc_material_repository] = override_get_material_repo

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


# ─── Helpers ────────────────────────────────────────────────────────────


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _admin(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


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


# ─── Auth (S3: admin-only writes) ──────────────────────────────────────


class TestMaterialsAuth:
    async def test_get_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/materials")
        assert response.status_code == 401

    async def test_get_cost_history_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/materials/m1/cost-history")
        assert response.status_code == 401

    async def test_post_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "Mantequilla"},
            headers=_auth(token),
        )
        assert response.status_code == 403


# ─── POST (RF-P2CC-01/02/03) ───────────────────────────────────────────


class TestCreateMaterial:
    async def test_creates_complete_material_with_derived_fields(
        self, client, db_session
    ):
        token = await _admin(client)
        body = await _create_material(
            client,
            token,
            internal_code="REF-001",
            unit_of_measure="kg",
            purchase_total_price="100",
            package_quantity="2",
            notes="lote 1",
        )
        # Derived by the server (RF-P2CC-02/03); money viaja en centavos (int).
        assert body["unit_cost"] == 5000
        assert body["status"] == "active"
        assert body["name"] == "Mantequilla"
        assert body["internal_code"] == "REF-001"
        assert body["unit_of_measure"] == "kg"
        assert body["purchase_total_price"] == 10000
        assert body["package_quantity"] == "2"
        assert body["notes"] == "lote 1"
        assert body["id"]
        assert body["created_at"] and body["updated_at"]

    async def test_creates_incomplete_material(self, client):
        token = await _admin(client)
        body = await _create_material(client, token)
        assert body["unit_cost"] is None
        assert body["status"] == "incomplete"
        assert body["purchase_total_price"] is None
        assert body["package_quantity"] is None

    async def test_package_quantity_zero_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "purchase_total_price": "10", "package_quantity": "0"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_negative_price_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "purchase_total_price": "-5"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_blank_name_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials", json={"name": "   "}, headers=_auth(token)
        )
        assert response.status_code == 422

    async def test_unit_cost_in_payload_rejected_422(self, client):
        # security #8: unit_cost nunca viene del cliente.
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "unit_cost": "999.99"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_status_in_payload_rejected_422(self, client):
        # security #8: status nunca viene del cliente.
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "status": "active"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_invalid_category_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "category_id": "no-existe"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_invalid_supplier_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/materials",
            json={"name": "X", "supplier_id": "no-existe"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_creates_with_valid_category_and_supplier(self, client):
        token = await _admin(client)
        cat = (
            await client.post(
                "/api/v1/calc/material-categories",
                json={"name": "Lacteos"},
                headers=_auth(token),
            )
        ).json()
        sup = (
            await client.post(
                "/api/v1/calc/suppliers",
                json={"name": "Distribuidora ABC"},
                headers=_auth(token),
            )
        ).json()
        body = await _create_material(
            client, token, category_id=cat["id"], supplier_id=sup["id"]
        )
        assert body["category_id"] == cat["id"]
        assert body["supplier_id"] == sup["id"]


# ─── GET (RF-P2CC-05) ──────────────────────────────────────────────────


class TestGetMaterial:
    async def test_get_by_id_returns_200(self, client):
        token = await _admin(client)
        created = await _create_material(
            client, token, internal_code="REF-002", purchase_total_price="10"
        )
        response = await client.get(
            f"/api/v1/calc/materials/{created['id']}", headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == created["id"]
        assert body["internal_code"] == "REF-002"

    async def test_get_unknown_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/materials/no-existe", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_list_search_by_name_accent_insensitive(self, client):
        token = await _admin(client)
        await _create_material(client, token, name="Azucar Moreno")
        await _create_material(client, token, name="Miel")
        response = await client.get(
            "/api/v1/calc/materials?q=azucar", headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Azucar Moreno"

    async def test_list_search_by_internal_code(self, client):
        token = await _admin(client)
        await _create_material(client, token, name="Miel", internal_code="REF-9")
        await _create_material(client, token, name="Mantequilla")
        response = await client.get(
            "/api/v1/calc/materials?q=ref-9", headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Miel"

    async def test_list_filter_by_status(self, client):
        token = await _admin(client)
        await _create_material(
            client,
            token,
            name="Activo",
            purchase_total_price="10",
            package_quantity="2",
        )
        await _create_material(client, token, name="Incompleto")
        for expected_name, expected_total in (("Activo", 1), ("Incompleto", 1)):
            response = await client.get(
                "/api/v1/calc/materials",
                params={
                    "q": expected_name,
                    "status": "active" if expected_name == "Activo" else "incomplete",
                },
                headers=_auth(token),
            )
            body = response.json()
            assert body["total"] == expected_total
            assert body["items"][0]["name"] == expected_name

    async def test_list_filter_by_category_id(self, client):
        token = await _admin(client)
        cat = (
            await client.post(
                "/api/v1/calc/material-categories",
                json={"name": "Lacteos"},
                headers=_auth(token),
            )
        ).json()
        await _create_material(
            client, token, name="Con categoria", category_id=cat["id"]
        )
        await _create_material(client, token, name="Sin categoria")
        response = await client.get(
            "/api/v1/calc/materials",
            params={"category_id": cat["id"]},
            headers=_auth(token),
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Con categoria"

    async def test_list_pagination(self, client):
        token = await _admin(client)
        for n in range(3):
            await _create_material(client, token, name=f"Material {n}")
        page1 = (
            await client.get(
                "/api/v1/calc/materials",
                params={"page": 1, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        page2 = (
            await client.get(
                "/api/v1/calc/materials",
                params={"page": 2, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        assert page1["total"] == 3
        assert len(page1["items"]) == 2
        assert page1["page"] == 1
        assert page2["total"] == 3
        assert len(page2["items"]) == 1


# ─── PATCH (RF-P2CC-01/02/04) ──────────────────────────────────────


class TestPatchMaterial:
    async def test_patch_price_recomputes_unit_cost(self, client):
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        response = await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"purchase_total_price": "150"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["purchase_total_price"] == 15000
        assert body["unit_cost"] == 7500
        assert body["status"] == "active"

    async def test_patch_without_fields_returns_422(self, client):
        token = await _admin(client)
        created = await _create_material(client, token)
        response = await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert "al menos un campo" in response.json()["detail"]

    async def test_patch_unknown_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.patch(
            "/api/v1/calc/materials/no-existe",
            json={"notes": "x"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_patch_invalid_fk_returns_404(self, client):
        token = await _admin(client)
        created = await _create_material(client, token)
        response = await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"category_id": "no-existe"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_patch_null_price_removes_it(self, client):
        # valor -> None: unit_cost -> None, status -> incomplete (RF-P2CC-04).
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        response = await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"purchase_total_price": None},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["purchase_total_price"] is None
        assert body["unit_cost"] is None
        assert body["status"] == "incomplete"


# ─── Cost history (RF-P2CC-04, append-only) ────────────────────────────


async def _history(client: AsyncClient, token: str, material_id: str) -> dict:
    response = await client.get(
        f"/api/v1/calc/materials/{material_id}/cost-history", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestCostHistory:
    async def test_create_with_price_records_initial_row(self, client):
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        body = await _history(client, token, created["id"])
        assert body["total"] == 1
        assert body["items"][0]["previous_unit_cost"] is None
        assert body["items"][0]["new_unit_cost"] == 5000
        assert body["items"][0]["changed_at"]

    async def test_create_incomplete_records_no_row(self, client):
        token = await _admin(client)
        created = await _create_material(client, token)
        body = await _history(client, token, created["id"])
        assert body["total"] == 0
        assert body["items"] == []

    async def test_patch_price_change_records_new_row_most_recent_first(self, client):
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"purchase_total_price": "150"},
            headers=_auth(token),
        )
        body = await _history(client, token, created["id"])
        assert body["total"] == 2
        # Mas recientes primero: el ultimo cambio arriba.
        assert body["items"][0]["previous_unit_cost"] == 5000
        assert body["items"][0]["new_unit_cost"] == 7500
        assert body["items"][1]["previous_unit_cost"] is None
        assert body["items"][1]["new_unit_cost"] == 5000

    async def test_patch_without_unit_cost_change_records_no_row(self, client):
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"notes": "cambio sin efecto en costo"},
            headers=_auth(token),
        )
        body = await _history(client, token, created["id"])
        assert body["total"] == 1

    async def test_patch_same_computed_cost_records_no_row(self, client):
        # Comparacion sobre el valor computado (re-roundeado), no strings crudos.
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="50",
            package_quantity="1",
        )
        await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"purchase_total_price": "50.00"},
            headers=_auth(token),
        )
        body = await _history(client, token, created["id"])
        assert body["total"] == 1

    async def test_patch_removing_price_records_row_with_new_none(self, client):
        token = await _admin(client)
        created = await _create_material(
            client,
            token,
            purchase_total_price="100",
            package_quantity="2",
        )
        await client.patch(
            f"/api/v1/calc/materials/{created['id']}",
            json={"purchase_total_price": None},
            headers=_auth(token),
        )
        body = await _history(client, token, created["id"])
        assert body["total"] == 2
        assert body["items"][0]["previous_unit_cost"] == 5000
        assert body["items"][0]["new_unit_cost"] is None

    async def test_history_of_unknown_material_returns_404(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/materials/no-existe/cost-history", headers=_auth(token)
        )
        assert response.status_code == 404


# ─── DELETE (S4: 409 en uso) ───────────────────────────────────────


class TestDeleteMaterial:
    async def test_delete_returns_204_then_404(self, client):
        token = await _admin(client)
        created = await _create_material(client, token)
        response = await client.delete(
            f"/api/v1/calc/materials/{created['id']}", headers=_auth(token)
        )
        assert response.status_code == 204
        again = await client.get(
            f"/api/v1/calc/materials/{created['id']}", headers=_auth(token)
        )
        assert again.status_code == 404

    async def test_delete_unknown_returns_404(self, client):
        token = await _admin(client)
        response = await client.delete(
            "/api/v1/calc/materials/no-existe", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_delete_in_use_returns_409_with_impacted_products(
        self, client, monkeypatch
    ):
        token = await _admin(client)
        created = await _create_material(client, token)

        async def fake_count_in_use(self, material_id: str) -> int:
            return 3

        monkeypatch.setattr(
            "data.repositories.calc.sql_calc_material_repository.SQLCalcMaterialRepository.count_in_use",
            fake_count_in_use,
        )
        response = await client.delete(
            f"/api/v1/calc/materials/{created['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"impacted_products": 3}
        # El material sigue ahi.
        still = await client.get(
            f"/api/v1/calc/materials/{created['id']}", headers=_auth(token)
        )
        assert still.status_code == 200


# ─── count_in_use real contra calc_materials (TODO(B8) completados) ─────


class TestForeignKeyInUse:
    async def test_category_referenced_by_material_cannot_be_deleted(self, client):
        token = await _admin(client)
        cat = (
            await client.post(
                "/api/v1/calc/material-categories",
                json={"name": "Lacteos"},
                headers=_auth(token),
            )
        ).json()
        await _create_material(client, token, category_id=cat["id"])
        response = await client.delete(
            f"/api/v1/calc/material-categories/{cat['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"in_use_by": 1}

    async def test_category_without_materials_can_be_deleted(self, client):
        token = await _admin(client)
        cat = (
            await client.post(
                "/api/v1/calc/material-categories",
                json={"name": "Secos"},
                headers=_auth(token),
            )
        ).json()
        response = await client.delete(
            f"/api/v1/calc/material-categories/{cat['id']}", headers=_auth(token)
        )
        assert response.status_code == 204

    async def test_supplier_referenced_by_material_cannot_be_deleted(self, client):
        token = await _admin(client)
        sup = (
            await client.post(
                "/api/v1/calc/suppliers",
                json={"name": "Distribuidora ABC"},
                headers=_auth(token),
            )
        ).json()
        await _create_material(client, token, supplier_id=sup["id"])
        response = await client.delete(
            f"/api/v1/calc/suppliers/{sup['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"in_use_by": 1}

    async def test_supplier_without_materials_can_be_deleted(self, client):
        token = await _admin(client)
        sup = (
            await client.post(
                "/api/v1/calc/suppliers",
                json={"name": "Proveedor Sol"},
                headers=_auth(token),
            )
        ).json()
        response = await client.delete(
            f"/api/v1/calc/suppliers/{sup['id']}", headers=_auth(token)
        )
        assert response.status_code == 204

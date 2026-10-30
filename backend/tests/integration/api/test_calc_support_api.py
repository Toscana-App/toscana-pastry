"""Integration tests for the Calc Support API (CRUD ABM endpoints).

Covers auth (401/403), CRUD operations, duplicate detection (409),
search + pagination, and validation (422) for:
  - /calc/material-categories
  - /calc/product-categories
  - /calc/suppliers
  - /calc/default-costs
(S2, S3).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data.accent import accent_fold
from data.db import get_db
from data.models import Base
from data.repositories.calc.sql_calc_default_cost_repository import SQLCalcDefaultCostRepository
from data.repositories.calc.sql_calc_material_category_repository import (
    SQLCalcMaterialCategoryRepository,
)
from data.repositories.calc.sql_calc_product_category_repository import (
    SQLCalcProductCategoryRepository,
)
from data.repositories.calc.sql_calc_settings_repository import SQLCalcSettingsRepository
from data.repositories.calc.sql_calc_supplier_repository import SQLCalcSupplierRepository
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.dependencies import get_user_repository
from api.v1.calc.dependencies import (
    get_calc_default_cost_repository,
    get_calc_material_category_repository,
    get_calc_product_category_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
from domain.models import User, UserRole
from sqlalchemy import event

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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_calc_settings_repository] = override_get_calc_settings_repository
    app.dependency_overrides[get_calc_material_category_repository] = override_get_material_category_repo
    app.dependency_overrides[get_calc_product_category_repository] = override_get_product_category_repo
    app.dependency_overrides[get_calc_supplier_repository] = override_get_supplier_repo
    app.dependency_overrides[get_calc_default_cost_repository] = override_get_default_cost_repo

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


async def _admin_token(client: AsyncClient) -> str:
    return await _token_for(client, "admin@example.com")


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


# ─── Auth tests (shared across all calc endpoints) ─────────────────────

@pytest.mark.asyncio
async def test_material_categories_requires_auth(client):
    """S3: sin session → 401."""
    response = await client.get("/api/v1/calc/material-categories")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_material_categories_forbidden_customer(client):
    """S3: no-admin → 403 en POST."""
    token = await _customer_token(client)
    response = await client.post(
        "/api/v1/calc/material-categories",
        json={"name": "Harinas"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_product_categories_requires_auth(client):
    response = await client.get("/api/v1/calc/product-categories")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_suppliers_requires_auth(client):
    response = await client.get("/api/v1/calc/suppliers")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_default_costs_requires_auth(client):
    response = await client.get("/api/v1/calc/default-costs")
    assert response.status_code == 401


# ─── Material Categories ────────────────────────────────────────────────

class TestMaterialCategories:
    _PATH = "/api/v1/calc/material-categories"

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """GET devuelve lista vacia al inicio."""
        token = await _admin_token(client)
        response = await client.get(
            self._PATH, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_create(self, client):
        """POST crea categoria con 201."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "Harinas", "description": "Todo tipo de harinas"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Harinas"
        assert body["description"] == "Todo tipo de harinas"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_create_duplicate_rejected(self, client):
        """POST nombre duplicado → 409."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(self._PATH, json={"name": "Harinas"}, headers=headers)
        dup = await client.post(self._PATH, json={"name": "harinas"}, headers=headers)
        assert dup.status_code == 409
        assert "nombre" in dup.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update(self, client):
        """PATCH actualiza categoria."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Harinas"}, headers=headers
        )
        cat_id = create.json()["id"]

        update = await client.patch(
            f"{self._PATH}/{cat_id}",
            json={"description": "Harinas especiales"},
            headers=headers,
        )
        assert update.status_code == 200
        assert update.json()["description"] == "Harinas especiales"

    @pytest.mark.asyncio
    async def test_update_empty_body_rejected(self, client):
        """PATCH sin campos → 422."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Harinas"}, headers=headers
        )
        cat_id = create.json()["id"]

        update = await client.patch(
            f"{self._PATH}/{cat_id}",
            json={},
            headers=headers,
        )
        assert update.status_code == 422

    @pytest.mark.asyncio
    async def test_delete(self, client):
        """DELETE elimina con 204."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Harinas"}, headers=headers
        )
        cat_id = create.json()["id"]

        delete = await client.delete(f"{self._PATH}/{cat_id}", headers=headers)
        assert delete.status_code == 204

        # El endpoint GET por id no existe; la lista no la incluye
        list_resp = await client.get(self._PATH, headers=headers)
        assert cat_id not in [item["id"] for item in list_resp.json()["items"]]

    @pytest.mark.asyncio
    async def test_search(self, client):
        """?q filtra por nombre."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(self._PATH, json={"name": "Harinas"}, headers=headers)
        await client.post(self._PATH, json={"name": "Levaduras"}, headers=headers)

        search = await client.get(f"{self._PATH}?q=harinas", headers=headers)
        assert search.status_code == 200
        assert search.json()["total"] == 1
        assert search.json()["items"][0]["name"] == "Harinas"

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        """?page&page_size paginados."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(5):
            await client.post(
                self._PATH, json={"name": f"Cat-{i}"}, headers=headers
            )

        page1 = await client.get(f"{self._PATH}?page=1&page_size=2", headers=headers)
        assert page1.json()["total"] == 5
        assert len(page1.json()["items"]) == 2
        assert page1.json()["page"] == 1

        page2 = await client.get(f"{self._PATH}?page=2&page_size=2", headers=headers)
        assert len(page2.json()["items"]) == 2
        assert page2.json()["page"] == 2

    @pytest.mark.asyncio
    async def test_create_blank_name_rejected(self, client):
        """POST name vacio → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_name_too_long_rejected(self, client):
        """POST name > 80 → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "a" * 81},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_description_too_long_rejected(self, client):
        """POST description > 200 → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "Cat", "description": "x" * 201},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


# ─── Product Categories ─────────────────────────────────────────────────

class TestProductCategories:
    _PATH = "/api/v1/calc/product-categories"

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        token = await _admin_token(client)
        response = await client.get(
            self._PATH, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_create(self, client):
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "Pasteles", "description": "Pasteles y tortas"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Pasteles"

    @pytest.mark.asyncio
    async def test_create_duplicate_rejected(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(self._PATH, json={"name": "Pasteles"}, headers=headers)
        dup = await client.post(self._PATH, json={"name": "pasteles"}, headers=headers)
        assert dup.status_code == 409

    @pytest.mark.asyncio
    async def test_update(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Pasteles"}, headers=headers
        )
        cat_id = create.json()["id"]

        update = await client.patch(
            f"{self._PATH}/{cat_id}",
            json={"description": "Tortas y pasteles"},
            headers=headers,
        )
        assert update.status_code == 200
        assert update.json()["description"] == "Tortas y pasteles"

    @pytest.mark.asyncio
    async def test_delete(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Pasteles"}, headers=headers
        )
        cat_id = create.json()["id"]

        delete = await client.delete(f"{self._PATH}/{cat_id}", headers=headers)
        assert delete.status_code == 204

    @pytest.mark.asyncio
    async def test_search(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(self._PATH, json={"name": "Pasteles"}, headers=headers)
        await client.post(self._PATH, json={"name": "Galletas"}, headers=headers)

        search = await client.get(f"{self._PATH}?q=pastel", headers=headers)
        assert search.json()["total"] == 1
        assert search.json()["items"][0]["name"] == "Pasteles"


# ─── Suppliers ──────────────────────────────────────────────────────────

class TestSuppliers:
    _PATH = "/api/v1/calc/suppliers"

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        token = await _admin_token(client)
        response = await client.get(
            self._PATH, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_create_minimal(self, client):
        """Solo name es obligatorio."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "Distribuidora Central"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Distribuidora Central"

    @pytest.mark.asyncio
    async def test_create_full(self, client):
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={
                "name": "Lacteos SA",
                "contact_name": "Juan Perez",
                "phone": "+5491112345678",
                "email": "ventas@lacteos.com",
                "notes": "Proveedor de quesos",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["contact_name"] == "Juan Perez"
        assert body["email"] == "ventas@lacteos.com"

    @pytest.mark.asyncio
    async def test_update(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Lacteos SA"}, headers=headers
        )
        sup_id = create.json()["id"]

        update = await client.patch(
            f"{self._PATH}/{sup_id}",
            json={"notes": "Nuevo proveedor de leche"},
            headers=headers,
        )
        assert update.status_code == 200
        assert update.json()["notes"] == "Nuevo proveedor de leche"

    @pytest.mark.asyncio
    async def test_delete(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH, json={"name": "Lacteos SA"}, headers=headers
        )
        sup_id = create.json()["id"]

        delete = await client.delete(f"{self._PATH}/{sup_id}", headers=headers)
        assert delete.status_code == 204

    @pytest.mark.asyncio
    async def test_search(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            self._PATH, json={"name": "Distribuidora Central"}, headers=headers
        )
        await client.post(
            self._PATH, json={"name": "Distribuidora Norte"}, headers=headers
        )

        search = await client.get(f"{self._PATH}?q=central", headers=headers)
        assert search.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_create_invalid_email_rejected(self, client):
        """Email invalido → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "A", "email": "not-an-email"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_blank_name_rejected(self, client):
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={"name": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


# ─── Default Costs ──────────────────────────────────────────────────────

class TestDefaultCosts:
    _PATH = "/api/v1/calc/default-costs"

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        token = await _admin_token(client)
        response = await client.get(
            self._PATH, headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_create_labor(self, client):
        """POST crea costo labor."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={
                "name": "Mano de obra",
                "type": "labor",
                "default_unit_cost_or_rate": "5000",
                "default_quantity_or_minutes": "60",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["type"] == "labor"
        # Money viaja en centavos (int); el str legacy "5000" = 50.000 unidades.
        assert body["default_unit_cost_or_rate"] == 500000

    @pytest.mark.asyncio
    async def test_create_extra_cost(self, client):
        """POST crea costo extra_cost."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={
                "name": "Gas",
                "type": "extra_cost",
                "default_unit_cost_or_rate": "1000",
                "default_quantity_or_minutes": "0",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["type"] == "extra_cost"

    @pytest.mark.asyncio
    async def test_update(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH,
            json={
                "name": "Mano de obra",
                "type": "labor",
                "default_unit_cost_or_rate": "5000",
                "default_quantity_or_minutes": "60",
            },
            headers=headers,
        )
        cost_id = create.json()["id"]

        update = await client.patch(
            f"{self._PATH}/{cost_id}",
            json={"default_unit_cost_or_rate": "6000"},
            headers=headers,
        )
        assert update.status_code == 200
        assert update.json()["default_unit_cost_or_rate"] == 600000

    @pytest.mark.asyncio
    async def test_delete(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            self._PATH,
            json={
                "name": "Gas",
                "type": "extra_cost",
                "default_unit_cost_or_rate": "1000",
                "default_quantity_or_minutes": "0",
            },
            headers=headers,
        )
        cost_id = create.json()["id"]

        delete = await client.delete(f"{self._PATH}/{cost_id}", headers=headers)
        assert delete.status_code == 204

    @pytest.mark.asyncio
    async def test_type_filter(self, client):
        """?type filtra por tipo."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            self._PATH,
            json={
                "name": "Mano de obra",
                "type": "labor",
                "default_unit_cost_or_rate": "5000",
                "default_quantity_or_minutes": "60",
            },
            headers=headers,
        )
        await client.post(
            self._PATH,
            json={
                "name": "Gas",
                "type": "extra_cost",
                "default_unit_cost_or_rate": "1000",
                "default_quantity_or_minutes": "0",
            },
            headers=headers,
        )

        labor = await client.get(
            f"{self._PATH}?type=labor", headers=headers
        )
        assert labor.json()["total"] == 1
        assert labor.json()["items"][0]["type"] == "labor"

    @pytest.mark.asyncio
    async def test_search(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            self._PATH,
            json={
                "name": "Mano de obra principal",
                "type": "labor",
                "default_unit_cost_or_rate": "5000",
                "default_quantity_or_minutes": "60",
            },
            headers=headers,
        )
        await client.post(
            self._PATH,
            json={
                "name": "Mano de obra secundaria",
                "type": "labor",
                "default_unit_cost_or_rate": "3000",
                "default_quantity_or_minutes": "30",
            },
            headers=headers,
        )

        search = await client.get(f"{self._PATH}?q=secundaria", headers=headers)
        assert search.json()["total"] == 1
        assert "secundaria" in search.json()["items"][0]["name"]

    @pytest.mark.asyncio
    async def test_create_negative_cost_rejected(self, client):
        """Costo negativo → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={
                "name": "A",
                "type": "labor",
                "default_unit_cost_or_rate": "-1",
                "default_quantity_or_minutes": "0",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_type_rejected(self, client):
        """Type invalido → 422."""
        token = await _admin_token(client)
        response = await client.post(
            self._PATH,
            json={
                "name": "A",
                "type": "invalid",
                "default_unit_cost_or_rate": "0",
                "default_quantity_or_minutes": "0",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(5):
            await client.post(
                self._PATH,
                json={
                    "name": f"Costo-{i}",
                    "type": "labor",
                    "default_unit_cost_or_rate": str(1000 * (i + 1)),
                    "default_quantity_or_minutes": "0",
                },
                headers=headers,
            )

        page = await client.get(
            f"{self._PATH}?page=1&page_size=2", headers=headers
        )
        assert page.json()["total"] == 5
        assert len(page.json()["items"]) == 2


# ─── Regression tests for PR #20 comment fixes ─────────────────────────


class TestAccentInsensitiveDuplicates:
    """Fix #2: get_by_name usa accent_fold para evitar duplicados con acentos.

    Regresion: "Harinas" y "Harin\u00e1s" no deben coexistir.
    """

    _PATH = "/api/v1/calc/material-categories"

    @pytest.mark.asyncio
    async def test_material_category_accent_duplicate_rejected(self, client):
        """POST "Harinas" + "Harin\u00e1s" → 409 en segundo."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(self._PATH, json={"name": "Harinas"}, headers=headers)
        dup = await client.post(
            self._PATH, json={"name": "Harin\u00e1s"}, headers=headers
        )
        assert dup.status_code == 409

    @pytest.mark.asyncio
    async def test_product_category_accent_duplicate_rejected(self, client):
        """POST "Levaduras" + "Levad\u00faras" → 409 en segundo."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        path = "/api/v1/calc/product-categories"
        await client.post(path, json={"name": "Levaduras"}, headers=headers)
        dup = await client.post(
            path, json={"name": "Levad\u00faras"}, headers=headers
        )
        assert dup.status_code == 409

class TestUpdatedAtRefreshOnPatch:
    """Fix #3: PATCH actualiza updated_at con nuevo timestamp.

    Regresion: el segundo PATCH debe tener updated_at > el del primero.
    """

    @pytest.mark.asyncio
    async def test_material_category_updated_at_refreshes(self, client):
        """PATCH actualiza updated_at a timestamp nuevo."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        path = "/api/v1/calc/material-categories"
        create = await client.post(path, json={"name": "TestUpdate"}, headers=headers)
        cat_id = create.json()["id"]
        first_updated = create.json()["updated_at"]

        import asyncio

        await asyncio.sleep(0.1)

        update = await client.patch(
            f"{path}/{cat_id}",
            json={"description": "updated"},
            headers=headers,
        )
        assert update.status_code == 200
        second_updated = update.json()["updated_at"]
        assert second_updated > first_updated

    @pytest.mark.asyncio
    async def test_product_category_updated_at_refreshes(self, client):
        """PATCH product-category actualiza updated_at."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        path = "/api/v1/calc/product-categories"
        create = await client.post(path, json={"name": "TestUpdate"}, headers=headers)
        cat_id = create.json()["id"]
        first_updated = create.json()["updated_at"]

        import asyncio

        await asyncio.sleep(0.1)

        update = await client.patch(
            f"{path}/{cat_id}",
            json={"description": "updated"},
            headers=headers,
        )
        assert update.status_code == 200
        second_updated = update.json()["updated_at"]
        assert second_updated > first_updated

    @pytest.mark.asyncio
    async def test_supplier_updated_at_refreshes(self, client):
        """PATCH supplier actualiza updated_at."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        path = "/api/v1/calc/suppliers"
        create = await client.post(
            path, json={"name": "TestUpdate"}, headers=headers
        )
        sup_id = create.json()["id"]
        first_updated = create.json()["updated_at"]

        import asyncio

        await asyncio.sleep(0.1)

        update = await client.patch(
            f"{path}/{sup_id}",
            json={"notes": "updated"},
            headers=headers,
        )
        assert update.status_code == 200
        second_updated = update.json()["updated_at"]
        assert second_updated > first_updated

    @pytest.mark.asyncio
    async def test_default_cost_updated_at_refreshes(self, client):
        """PATCH default-cost actualiza updated_at."""
        token = await _admin_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        path = "/api/v1/calc/default-costs"
        create = await client.post(
            path,
            json={
                "name": "TestUpdate",
                "type": "labor",
                "default_unit_cost_or_rate": "1000",
                "default_quantity_or_minutes": "0",
            },
            headers=headers,
        )
        cost_id = create.json()["id"]
        first_updated = create.json()["updated_at"]

        import asyncio

        await asyncio.sleep(0.1)

        update = await client.patch(
            f"{path}/{cost_id}",
            json={"status": "inactive"},
            headers=headers,
        )
        assert update.status_code == 200
        second_updated = update.json()["updated_at"]
        assert second_updated > first_updated


import pytest
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


async def _create_product(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {"name": "Brownie"}
    payload.update(overrides)
    response = await client.post(
        "/api/v1/calc/products", json=payload, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _set_settings(client: AsyncClient, token: str, **overrides) -> dict:
    payload = {
        "business_name": "Toscana Pastry",
        "main_currency_name": "Peso",
        "main_currency_symbol": "$",
        "default_margin_percent": "30",
        "default_discount_percent": "0",
        "default_tax_percent": "19",
        "rounding_mode": "none",
    }
    payload.update(overrides)
    response = await client.put(
        "/api/v1/calc/settings", json=payload, headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _create_product_category(
    client: AsyncClient, token: str, name: str = "Postres"
) -> dict:
    response = await client.post(
        "/api/v1/calc/product-categories", json={"name": name}, headers=_auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _parity_material(client: AsyncClient, token: str) -> dict:
    return await _create_material(
        client,
        token,
        name="Mantequilla",
        unit_of_measure="kg",
        purchase_total_price=4568000,
        package_quantity="100",
    )


def _parity_payload(material_id: str, **overrides) -> dict:
    payload = {
        "name": "Brownie Clasico",
        "discount_percent": "10",
        "materials": [{"material_id": material_id, "quantity_used": "2.5"}],
        "labor": [
            {
                "activity_name": "Coccion",
                "hourly_rate": 150000,
                "minutes_required": "45",
            }
        ],
        "extra_costs": [
            {"concept_name": "Embalaje", "unit_cost": 32010, "quantity": "3"}
        ],
    }
    payload.update(overrides)
    return payload


PARITY_COSTS = {
    "product_total_cost": 322730,
    "profit_amount": 138313,
    "discount_amount": -46104,
    "adjusted_profit_amount": 92209,
    "tax_amount": 78838,
    "final_sale_price": 493777,
}




class TestProductsAuth:
    async def test_list_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/products")
        assert response.status_code == 401

    async def test_detail_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/products/p1")
        assert response.status_code == 401

    async def test_versions_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/products/p1/versions")
        assert response.status_code == 401

    async def test_post_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.post(
            "/api/v1/calc/products", json={"name": "Brownie"}, headers=_auth(token)
        )
        assert response.status_code == 403

    async def test_patch_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.patch(
            "/api/v1/calc/products/p1", json={"name": "X"}, headers=_auth(token)
        )
        assert response.status_code == 403

    async def test_delete_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.delete(
            "/api/v1/calc/products/p1", headers=_auth(token)
        )
        assert response.status_code == 403

    async def test_recalculate_as_customer_returns_403(self, client):
        token = await _token_for(client, "customer@example.com")
        response = await client.post(
            "/api/v1/calc/products/p1/recalculate", headers=_auth(token)
        )
        assert response.status_code == 403




class TestCreateProduct:
    async def test_parity_case_full_breakdown(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        assert material["unit_cost"] == 45680
        body = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        assert body["costs"] == PARITY_COSTS
        assert body["product"]["id"]
        assert body["product"]["status"] == "draft"
        from decimal import Decimal

        assert Decimal(body["product"]["margin_percent"]) == Decimal("30")
        assert Decimal(body["product"]["discount_percent"]) == Decimal("10")
        assert Decimal(body["product"]["tax_percent"]) == Decimal("19")

    async def test_parity_snapshots_resolved_by_server(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        body = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        material_lines = body["product_lines"]["materials"]
        assert material_lines[0]["material_name"] == "Mantequilla"
        assert material_lines[0]["unit_of_measure_snapshot"] == "kg"
        assert material_lines[0]["unit_cost_snapshot"] == 45680
        assert material_lines[0]["line_total_cost"] == 114200
        assert material_lines[0]["sort_order"] == 0

    async def test_parity_final_per_rounding_mode_via_settings(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        for mode, expected_final in (
            ("none", 493777),
            ("integer", 493800),
            ("multiple_10", 494000),
            ("commercial_99", 499900),
        ):
            await _set_settings(client, token, rounding_mode=mode)
            response = await client.get(
                f"/api/v1/calc/products/{product_id}", headers=_auth(token)
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["costs"]["final_sale_price"] == expected_final
            for key, value in PARITY_COSTS.items():
                if key != "final_sale_price":
                    assert body["costs"][key] == value

    async def test_incomplete_material_snapshots_zero_without_error(self, client):
        token = await _admin(client)
        material = await _create_material(client, token, name="Harina")
        assert material["unit_cost"] is None
        body = await _create_product(
            client,
            token,
            name="Pan Simple",
            materials=[{"material_id": material["id"], "quantity_used": "2"}],
            labor=[
                {
                    "activity_name": "Amasado",
                    "hourly_rate": 100000,
                    "minutes_required": "60",
                }
            ],
            extra_costs=[],
        )
        line = body["product_lines"]["materials"][0]
        assert line["unit_cost_snapshot"] == 0
        assert line["line_total_cost"] == 0
        assert body["costs"]["product_total_cost"] == 100000
        assert body["costs"]["final_sale_price"] == 170000

    async def test_explicit_percents_are_used(self, client):
        token = await _admin(client)
        body = await _create_product(
            client,
            token,
            margin_percent="50",
            discount_percent="10",
            tax_percent="0",
        )
        from decimal import Decimal

        assert Decimal(body["product"]["margin_percent"]) == Decimal("50")
        assert Decimal(body["product"]["discount_percent"]) == Decimal("10")
        assert Decimal(body["product"]["tax_percent"]) == Decimal("0")

    async def test_settings_defaults_applied_when_payload_omits_percents(
        self, client
    ):
        token = await _admin(client)
        await _set_settings(
            client,
            token,
            default_margin_percent="40",
            default_discount_percent="5",
            default_tax_percent="21",
        )
        body = await _create_product(client, token)
        from decimal import Decimal

        assert Decimal(body["product"]["margin_percent"]) == Decimal("40")
        assert Decimal(body["product"]["discount_percent"]) == Decimal("5")
        assert Decimal(body["product"]["tax_percent"]) == Decimal("21")

    async def test_creates_with_category_and_sku(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token)
        body = await _create_product(client, token, sku="BR-001", category_id=cat["id"])
        assert body["product"]["sku"] == "BR-001"
        assert body["product"]["category_id"] == cat["id"]

    async def test_unknown_material_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={
                "name": "X",
                "materials": [
                    {"material_id": "no-existe", "quantity_used": "1"}
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_unknown_category_id_returns_404(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "X", "category_id": "no-existe"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_duplicate_sku_returns_409(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Uno", sku="SKU-1")
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "Dos", "sku": "sku-1"},
            headers=_auth(token),
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "SKU ya en uso"}

    async def test_duplicate_sku_accent_insensitive_returns_409(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Uno", sku="SKU-Ñ1")
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "Dos", "sku": "sku-n1"},
            headers=_auth(token),
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "SKU ya en uso"}

    async def test_costs_in_payload_rejected_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "X", "costs": {"final_sale_price": 100}},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_snapshot_field_in_material_line_rejected_422(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        response = await client.post(
            "/api/v1/calc/products",
            json={
                "name": "X",
                "materials": [
                    {
                        "material_id": material["id"],
                        "quantity_used": "1",
                        "unit_cost_snapshot": 99900,
                    }
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_line_total_cost_in_payload_rejected_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={
                "name": "X",
                "labor": [
                    {
                        "activity_name": "X",
                        "hourly_rate": 1000,
                        "minutes_required": "5",
                        "line_total_cost": 100,
                    }
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_negative_quantity_returns_422(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        response = await client.post(
            "/api/v1/calc/products",
            json={
                "name": "X",
                "materials": [
                    {"material_id": material["id"], "quantity_used": "-1"}
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_negative_labor_rate_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={
                "name": "X",
                "labor": [
                    {
                        "activity_name": "X",
                        "hourly_rate": -1000,
                        "minutes_required": "5",
                    }
                ],
            },
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_percent_above_100_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "X", "margin_percent": "150"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_invalid_status_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products",
            json={"name": "X", "status": "bogus"},
            headers=_auth(token),
        )
        assert response.status_code == 422

    async def test_blank_name_returns_422(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products", json={"name": "   "}, headers=_auth(token)
        )
        assert response.status_code == 422




class TestGetProduct:
    async def test_detail_returns_product_lines_and_costs(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        response = await client.get(
            f"/api/v1/calc/products/{product_id}", headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["product"]["id"] == product_id
        assert len(body["materials"]) == 1
        assert len(body["labor"]) == 1
        assert len(body["extra_costs"]) == 1
        assert body["costs"] == PARITY_COSTS
        assert "versions" not in body

    async def test_detail_include_versions(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        product_id = created["product"]["id"]
        response = await client.get(
            f"/api/v1/calc/products/{product_id}",
            params={"include_versions": "true"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert "versions" in body
        assert body["versions"] == []

    async def test_detail_unknown_returns_404(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/products/no-existe", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_detail_deleted_returns_404(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        await client.delete(
            f"/api/v1/calc/products/{created['product']['id']}", headers=_auth(token)
        )
        response = await client.get(
            f"/api/v1/calc/products/{created['product']['id']}", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_list_search_by_name_and_sku_accent_insensitive(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Torta de Cafe")
        await _create_product(client, token, name="Pan", sku="CAFE-SKU")
        await _create_product(client, token, name="Pastel de Limon")
        response = await client.get(
            "/api/v1/calc/products", params={"q": "cafe"}, headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert {item["name"] for item in body["items"]} == {
            "Torta de Cafe",
            "Pan",
        }

    async def test_list_filter_by_status(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Activo", status="active")
        await _create_product(client, token, name="Borrador")
        for status, expected_name in (("active", "Activo"), ("draft", "Borrador")):
            response = await client.get(
                "/api/v1/calc/products",
                params={"status": status},
                headers=_auth(token),
            )
            body = response.json()
            assert body["total"] == 1
            assert body["items"][0]["name"] == expected_name

    async def test_list_filter_by_category(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token, name="Tortas")
        await _create_product(client, token, name="Con Cat", category_id=cat["id"])
        await _create_product(client, token, name="Sin Cat")
        response = await client.get(
            "/api/v1/calc/products",
            params={"category_id": cat["id"]},
            headers=_auth(token),
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "Con Cat"

    async def test_list_fixed_name_order_and_pagination(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Zebra")
        await _create_product(client, token, name="Alpha")
        await _create_product(client, token, name="Mango")
        page1 = (
            await client.get(
                "/api/v1/calc/products",
                params={"page": 1, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        page2 = (
            await client.get(
                "/api/v1/calc/products",
                params={"page": 2, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        assert page1["total"] == 3
        assert [item["name"] for item in page1["items"]] == ["Alpha", "Mango"]
        assert [item["name"] for item in page2["items"]] == ["Zebra"]

    async def test_list_excludes_deleted(self, client):
        token = await _admin(client)
        created = await _create_product(client, token, name="Temporal")
        other = await _create_product(client, token, name="Permanente")
        await client.delete(
            f"/api/v1/calc/products/{created['product']['id']}", headers=_auth(token)
        )
        body = (
            await client.get("/api/v1/calc/products", headers=_auth(token))
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == other["product"]["id"]




class TestPatchProduct:
    async def test_patch_name_returns_product_and_costs(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        response = await client.patch(
            f"/api/v1/calc/products/{product_id}",
            json={"name": "Brownie Deluxe"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["product"]["name"] == "Brownie Deluxe"
        assert body["costs"] == PARITY_COSTS

    async def test_patch_without_fields_returns_422(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        response = await client.patch(
            f"/api/v1/calc/products/{created['product']['id']}",
            json={},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert "al menos un campo" in response.json()["detail"]

    @pytest.mark.parametrize("field", ["name", "margin_percent"])
    async def test_patch_explicit_null_on_non_nullable_returns_422(
        self, client, field
    ):
        token = await _admin(client)
        created = await _create_product(client, token)
        response = await client.patch(
            f"/api/v1/calc/products/{created['product']['id']}",
            json={field: None},
            headers=_auth(token),
        )
        assert response.status_code == 422
        assert field in response.json()["detail"]

    async def test_patch_unknown_returns_404(self, client):
        token = await _admin(client)
        response = await client.patch(
            "/api/v1/calc/products/no-existe",
            json={"name": "X"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_patch_invalid_category_returns_404(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        response = await client.patch(
            f"/api/v1/calc/products/{created['product']['id']}",
            json={"category_id": "no-existe"},
            headers=_auth(token),
        )
        assert response.status_code == 404

    async def test_patch_sku_owned_by_other_returns_409(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="Uno", sku="OCC-1")
        other = await _create_product(client, token, name="Dos")
        response = await client.patch(
            f"/api/v1/calc/products/{other['product']['id']}",
            json={"sku": "occ-1"},
            headers=_auth(token),
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "SKU ya en uso"}

    async def test_patch_own_sku_is_allowed(self, client):
        token = await _admin(client)
        created = await _create_product(client, token, sku="MIA-1")
        response = await client.patch(
            f"/api/v1/calc/products/{created['product']['id']}",
            json={"sku": "mia-1"},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert response.json()["product"]["sku"] == "mia-1"

    async def test_patch_materials_replaces_set_and_refreshes_snapshots(
        self, client
    ):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        await client.patch(
            f"/api/v1/calc/materials/{material['id']}",
            json={"purchase_total_price": 1000000, "package_quantity": "10"},
            headers=_auth(token),
        )
        response = await client.patch(
            f"/api/v1/calc/products/{product_id}",
            json={"materials": [{"material_id": material["id"], "quantity_used": "1"}]},
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        detail = (
            await client.get(
                f"/api/v1/calc/products/{product_id}", headers=_auth(token)
            )
        ).json()
        assert len(detail["materials"]) == 1
        line = detail["materials"][0]
        assert line["unit_cost_snapshot"] == 100000
        assert line["line_total_cost"] == 100000
        assert body["costs"]["product_total_cost"] == 308530
        assert body["costs"]["final_sale_price"] == 472050

    async def test_patch_empty_list_empties_only_that_type(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        response = await client.patch(
            f"/api/v1/calc/products/{product_id}",
            json={"materials": []},
            headers=_auth(token),
        )
        assert response.status_code == 200
        detail = (
            await client.get(
                f"/api/v1/calc/products/{product_id}", headers=_auth(token)
            )
        ).json()
        assert detail["materials"] == []
        assert len(detail["labor"]) == 1
        assert len(detail["extra_costs"]) == 1
        assert detail["costs"]["product_total_cost"] == 208530
        assert detail["costs"]["final_sale_price"] == 319051

    async def test_patch_without_line_keys_keeps_lines(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        await client.patch(
            f"/api/v1/calc/products/{product_id}",
            json={"notes": "cambio sin lineas"},
            headers=_auth(token),
        )
        detail = (
            await client.get(
                f"/api/v1/calc/products/{product_id}", headers=_auth(token)
            )
        ).json()
        assert len(detail["materials"]) == 1
        assert len(detail["labor"]) == 1
        assert len(detail["extra_costs"]) == 1




class TestDeleteProduct:
    async def test_delete_returns_204_then_404(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        product_id = created["product"]["id"]
        response = await client.delete(
            f"/api/v1/calc/products/{product_id}", headers=_auth(token)
        )
        assert response.status_code == 204
        again = await client.get(
            f"/api/v1/calc/products/{product_id}", headers=_auth(token)
        )
        assert again.status_code == 404

    async def test_delete_unknown_returns_404(self, client):
        token = await _admin(client)
        response = await client.delete(
            "/api/v1/calc/products/no-existe", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_deleted_sku_becomes_available_again(self, client):
        token = await _admin(client)
        deleted = await _create_product(client, token, name="Uno", sku="REL-1")
        await client.delete(
            f"/api/v1/calc/products/{deleted['product']['id']}",
            headers=_auth(token),
        )
        body = await _create_product(client, token, name="Dos", sku="rel-1")
        assert body["product"]["sku"] == "rel-1"




class TestRecalculate:
    async def test_recalculate_without_change_creates_no_version(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        response = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["costs"] == PARITY_COSTS
        assert body["product"]["last_recalculated_at"] is not None
        versions = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert versions["total"] == 0

    async def test_recalculate_after_price_change_creates_version(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        await client.patch(
            f"/api/v1/calc/materials/{material['id']}",
            json={"purchase_total_price": 1000000, "package_quantity": "10"},
            headers=_auth(token),
        )
        response = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["costs"]["product_total_cost"] == 458530
        assert body["costs"]["final_sale_price"] == 701551
        detail = (
            await client.get(
                f"/api/v1/calc/products/{product_id}", headers=_auth(token)
            )
        ).json()
        assert detail["materials"][0]["unit_cost_snapshot"] == 100000
        assert detail["materials"][0]["line_total_cost"] == 250000
        versions = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert versions["total"] == 1
        assert versions["items"][0]["version_number"] == 1
        assert versions["items"][0]["final_sale_price"] == 701551
        assert versions["items"][0]["product_total_cost"] == 458530
        assert versions["items"][0]["changed_at"]

    async def test_recalculate_twice_creates_only_one_version(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        await client.patch(
            f"/api/v1/calc/materials/{material['id']}",
            json={"purchase_total_price": 1000000, "package_quantity": "10"},
            headers=_auth(token),
        )
        await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        versions = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert versions["total"] == 1

    async def test_post_and_patch_create_no_versions(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        product_id = created["product"]["id"]
        await client.patch(
            f"/api/v1/calc/products/{product_id}",
            json={"name": "Brownie V2"},
            headers=_auth(token),
        )
        versions = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert versions["total"] == 0

    async def test_recalculate_unknown_returns_404(self, client):
        token = await _admin(client)
        response = await client.post(
            "/api/v1/calc/products/no-existe/recalculate", headers=_auth(token)
        )
        assert response.status_code == 404

    async def test_recalculate_deleted_returns_404(self, client):
        token = await _admin(client)
        created = await _create_product(client, token)
        product_id = created["product"]["id"]
        await client.delete(
            f"/api/v1/calc/products/{product_id}", headers=_auth(token)
        )
        response = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        assert response.status_code == 404




class TestProductVersions:
    async def test_versions_listed_most_recent_first(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]

        async def bump_and_recalculate(price: int):
            await client.patch(
                f"/api/v1/calc/materials/{material['id']}",
                json={"purchase_total_price": price, "package_quantity": "10"},
                headers=_auth(token),
            )
            response = await client.post(
                f"/api/v1/calc/products/{product_id}/recalculate",
                headers=_auth(token),
            )
            assert response.status_code == 200

        await bump_and_recalculate(1000000)
        await bump_and_recalculate(2000000)
        body = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert body["total"] == 2
        assert [item["version_number"] for item in body["items"]] == [2, 1]
        assert body["items"][0]["final_sale_price"] == 1084051
        assert body["items"][1]["final_sale_price"] == 701551

    async def test_versions_pagination(self, client):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]
        for price in (1000000, 2000000):
            await client.patch(
                f"/api/v1/calc/materials/{material['id']}",
                json={"purchase_total_price": price, "package_quantity": "10"},
                headers=_auth(token),
            )
            await client.post(
                f"/api/v1/calc/products/{product_id}/recalculate",
                headers=_auth(token),
            )
        page1 = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                params={"page": 1, "page_size": 1},
                headers=_auth(token),
            )
        ).json()
        page2 = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                params={"page": 2, "page_size": 1},
                headers=_auth(token),
            )
        ).json()
        assert page1["total"] == 2
        assert len(page1["items"]) == 1
        assert page1["items"][0]["version_number"] == 2
        assert page2["items"][0]["version_number"] == 1

    async def test_versions_of_unknown_product_returns_404(self, client):
        token = await _admin(client)
        response = await client.get(
            "/api/v1/calc/products/no-existe/versions", headers=_auth(token)
        )
        assert response.status_code == 404




class TestCountInUse:
    async def test_material_in_product_cannot_be_deleted(self, client):
        token = await _admin(client)
        material = await _create_material(client, token, name="Leche")
        await _create_product(
            client,
            token,
            name="Pan con Leche",
            materials=[{"material_id": material["id"], "quantity_used": "1"}],
        )
        response = await client.delete(
            f"/api/v1/calc/materials/{material['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"impacted_products": 1}

    async def test_material_distinct_products_counted_once_each(self, client):
        token = await _admin(client)
        material = await _create_material(client, token, name="Huevo")
        for name in ("Pan A", "Pan B"):
            await _create_product(
                client,
                token,
                name=name,
                materials=[{"material_id": material["id"], "quantity_used": "2"}],
            )
        response = await client.delete(
            f"/api/v1/calc/materials/{material['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"impacted_products": 2}

    async def test_material_of_deleted_product_can_be_deleted(self, client):
        token = await _admin(client)
        material = await _create_material(client, token, name="Sal")
        product = await _create_product(
            client,
            token,
            name="Pan con Sal",
            materials=[{"material_id": material["id"], "quantity_used": "1"}],
        )
        await client.delete(
            f"/api/v1/calc/products/{product['product']['id']}",
            headers=_auth(token),
        )
        response = await client.delete(
            f"/api/v1/calc/materials/{material['id']}", headers=_auth(token)
        )
        assert response.status_code == 204

    async def test_product_category_in_use_cannot_be_deleted(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token, name="Panaderia")
        await _create_product(
            client, token, name="Pan Blanco", category_id=cat["id"]
        )
        response = await client.delete(
            f"/api/v1/calc/product-categories/{cat['id']}", headers=_auth(token)
        )
        assert response.status_code == 409
        assert response.json() == {"in_use_by": 1}

    async def test_product_category_without_products_can_be_deleted(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token, name="Vacio")
        response = await client.delete(
            f"/api/v1/calc/product-categories/{cat['id']}", headers=_auth(token)
        )
        assert response.status_code == 204

    async def test_product_category_freed_by_deleted_product(self, client):
        token = await _admin(client)
        cat = await _create_product_category(client, token, name="Tortitas")
        product = await _create_product(
            client, token, name="Torta", category_id=cat["id"]
        )
        await client.delete(
            f"/api/v1/calc/products/{product['product']['id']}",
            headers=_auth(token),
        )
        response = await client.delete(
            f"/api/v1/calc/product-categories/{cat['id']}", headers=_auth(token)
        )
        assert response.status_code == 204




class TestVersionUniqueness:
    async def test_duplicate_version_number_raises_integrity_error(
        self, db_session
    ):
        import datetime

        from sqlalchemy.exc import IntegrityError

        from data.models import CalcProductORM, CalcProductVersionORM

        db_session.add(
            CalcProductORM(
                id="p1",
                name="P1",
                margin_percent="30",
                discount_percent="0",
                tax_percent="0",
                status="active",
            )
        )
        await db_session.flush()

        def _version(row_id: str) -> CalcProductVersionORM:
            return CalcProductVersionORM(
                id=row_id,
                product_id="p1",
                version_number=1,
                product_total_cost="1",
                profit_amount="1",
                discount_amount="0",
                adjusted_profit_amount="1",
                tax_amount="0",
                final_sale_price="2",
                changed_at=datetime.datetime.now(datetime.UTC),
            )

        db_session.add(_version("v1"))
        await db_session.flush()
        db_session.add(_version("v2"))
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_recalculate_returns_409_on_version_conflict(
        self, client, monkeypatch
    ):
        token = await _admin(client)
        material = await _parity_material(client, token)
        created = await _create_product(
            client, token, **_parity_payload(material["id"])
        )
        product_id = created["product"]["id"]

        async def _bump_price():
            await client.patch(
                f"/api/v1/calc/materials/{material['id']}",
                json={"purchase_total_price": 1000000, "package_quantity": "10"},
                headers=_auth(token),
            )

        await _bump_price()
        first = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        assert first.status_code == 200

        await client.patch(
            f"/api/v1/calc/materials/{material['id']}",
            json={"purchase_total_price": 2000000, "package_quantity": "10"},
            headers=_auth(token),
        )

        async def _existing_number(self, product_id):
            return 1

        monkeypatch.setattr(
            SQLCalcProductRepository, "_next_version_number", _existing_number
        )
        response = await client.post(
            f"/api/v1/calc/products/{product_id}/recalculate",
            headers=_auth(token),
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "version_conflict"
        monkeypatch.undo()
        versions = (
            await client.get(
                f"/api/v1/calc/products/{product_id}/versions",
                headers=_auth(token),
            )
        ).json()
        assert versions["total"] == 1

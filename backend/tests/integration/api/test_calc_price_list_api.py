"""Integration tests for the price list endpoints (RF-P3CC-04).

Covers: `GET /calc/products/price-list` (only active + not deleted,
fixed name order, q over name AND SKU with accent_fold, category
filter, pagination, enriched item with `category_name` and
engine-computed `final_sale_price` with the settings `rounding_mode`)
and `GET /calc/products/price-list/export` (exact spec CSV header,
rows in name order, `cost` pre-rounding, empty category, proper
quoting, `text/csv` + attachment headers, no pagination).
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
    get_calc_material_category_repository,
    get_calc_material_repository,
    get_calc_product_category_repository,
    get_calc_product_repository,
    get_calc_settings_repository,
    get_calc_supplier_repository,
)
from data.accent import accent_fold
from data.db import get_db
from data.models import Base
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


async def _seed_price_list(client: AsyncClient, token: str) -> dict:
    """Material 100.00 + 3 activos (2 con categoria, 1 sin) + 1 draft +
    1 archived + 1 eliminado.

    Valores esperados (motor: discount 0, tax 19, rounding none),
    calculados a mano:
      Alpha (qty1, m50): cost 100.00, final 238.00, cat "Postres"
      Beta  (qty2, m30): cost 200.00, final 339.99, sin categoria
      Gamma (qty3, m10): cost 300.00, final 396.66, cat "Postres"
    """
    material = await _create_material(
        client, token,
        unit_of_measure="kg",
        purchase_total_price=10000, package_quantity="1",
    )
    cat = await _create_product_category(client, token, name="Postres")
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
    await _create_product(
        client,
        token,
        name="Beta",
        status="active",
        margin_percent="30",
        materials=[{"material_id": material["id"], "quantity_used": "2"}],
    )
    await _create_product(
        client,
        token,
        name="Gamma",
        sku="TORTA-01",
        status="active",
        category_id=cat["id"],
        margin_percent="10",
        materials=[{"material_id": material["id"], "quantity_used": "3"}],
    )
    await _create_product(
        client,
        token,
        name="Delta",
        status="draft",
        materials=[{"material_id": material["id"], "quantity_used": "1"}],
    )
    await _create_product(
        client,
        token,
        name="Epsilon",
        status="archived",
        materials=[{"material_id": material["id"], "quantity_used": "1"}],
    )
    zeta = await _create_product(
        client,
        token,
        name="Zeta",
        status="active",
        materials=[{"material_id": material["id"], "quantity_used": "1"}],
    )
    await client.delete(
        f"/api/v1/calc/products/{zeta['product']['id']}", headers=_auth(token)
    )
    return {"cat": cat, "material": material}


# ─── Auth (S3/D2) ──────────────────────────────────────────────────────


class TestPriceListAuth:
    async def test_price_list_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/products/price-list")
        assert response.status_code == 401

    async def test_export_without_session_returns_401(self, client):
        response = await client.get("/api/v1/calc/products/price-list/export")
        assert response.status_code == 401

    async def test_any_user_can_read(self, client):
        """GETs con get_current_user: un customer autenticado puede leer."""
        token = await _token_for(client, "customer@example.com")
        response = await client.get(
            "/api/v1/calc/products/price-list", headers=_auth(token)
        )
        assert response.status_code == 200


# ─── GET /price-list (RF-P3CC-04) ──────────────────────────────────────


class TestPriceList:
    async def test_returns_only_active_in_name_order(self, client):
        """Solo los 3 activos (draft/archived/eliminados fuera), orden
        fijo por nombre."""
        token = await _admin(client)
        await _seed_price_list(client, token)
        response = await client.get(
            "/api/v1/calc/products/price-list", headers=_auth(token)
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert [item["name"] for item in body["items"]] == [
            "Alpha",
            "Beta",
            "Gamma",
        ]

    async def test_item_shape_and_engine_values(self, client):
        """Item: id, name, sku, category_id, category_name (null si no
        hay categoria), montos calculados por el motor."""
        token = await _admin(client)
        seed = await _seed_price_list(client, token)
        body = (
            await client.get(
                "/api/v1/calc/products/price-list", headers=_auth(token)
            )
        ).json()
        by_name = {item["name"]: item for item in body["items"]}
        alpha = by_name["Alpha"]
        assert set(alpha.keys()) == {
            "id",
            "name",
            "sku",
            "category_id",
            "category_name",
            "product_total_cost",
            "final_sale_price",
            "margin_percent",
        }
        assert alpha["sku"] == "AL-1"
        assert alpha["category_id"] == seed["cat"]["id"]
        assert alpha["category_name"] == "Postres"
        assert alpha["product_total_cost"] == 10000
        assert alpha["final_sale_price"] == 23800
        assert float(alpha["margin_percent"]) == 50.0
        beta = by_name["Beta"]
        assert beta["category_id"] is None
        assert beta["category_name"] is None
        assert beta["product_total_cost"] == 20000
        assert beta["final_sale_price"] == 33999
        gamma = by_name["Gamma"]
        assert gamma["product_total_cost"] == 30000
        assert gamma["final_sale_price"] == 39666

    async def test_final_price_uses_settings_rounding(self, client):
        """final_sale_price con el redondeo del rounding_mode de
        settings (integer): 238.00->238, 339.99->340, 396.66->397."""
        token = await _admin(client)
        await _seed_price_list(client, token)
        await _set_settings(client, token, rounding_mode="integer")
        body = (
            await client.get(
                "/api/v1/calc/products/price-list", headers=_auth(token)
            )
        ).json()
        finals = {item["name"]: item["final_sale_price"] for item in body["items"]}
        assert finals == {"Alpha": 23800, "Beta": 34000, "Gamma": 39700}

    async def test_q_searches_name_and_sku_accent_insensitive(self, client):
        token = await _admin(client)
        await _seed_price_list(client, token)
        by_sku = (
            await client.get(
                "/api/v1/calc/products/price-list",
                params={"q": "torta"},
                headers=_auth(token),
            )
        ).json()
        assert by_sku["total"] == 1
        assert by_sku["items"][0]["name"] == "Gamma"
        by_name = (
            await client.get(
                "/api/v1/calc/products/price-list",
                params={"q": "alp"},
                headers=_auth(token),
            )
        ).json()
        assert by_name["total"] == 1
        assert by_name["items"][0]["name"] == "Alpha"

    async def test_category_filter(self, client):
        token = await _admin(client)
        seed = await _seed_price_list(client, token)
        body = (
            await client.get(
                "/api/v1/calc/products/price-list",
                params={"category_id": seed["cat"]["id"]},
                headers=_auth(token),
            )
        ).json()
        assert body["total"] == 2
        assert [item["name"] for item in body["items"]] == ["Alpha", "Gamma"]

    async def test_pagination(self, client):
        token = await _admin(client)
        await _seed_price_list(client, token)
        page1 = (
            await client.get(
                "/api/v1/calc/products/price-list",
                params={"page": 1, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        page2 = (
            await client.get(
                "/api/v1/calc/products/price-list",
                params={"page": 2, "page_size": 2},
                headers=_auth(token),
            )
        ).json()
        assert page1["total"] == 3
        assert [item["name"] for item in page1["items"]] == ["Alpha", "Beta"]
        assert [item["name"] for item in page2["items"]] == ["Gamma"]


# ─── GET /price-list/export (CSV, RF-P3CC-04) ──────────────────────────


class TestPriceListExport:
    async def test_csv_header_rows_and_values(self, client):
        """Header exacto de la spec + 3 filas en orden por nombre;
        `cost` pre-redondeo (2 decimales); categoria vacia si no hay."""
        token = await _admin(client)
        await _seed_price_list(client, token)
        response = await client.get(
            "/api/v1/calc/products/price-list/export", headers=_auth(token)
        )
        assert response.status_code == 200
        text = response.text
        lines = text.split("\n")
        assert lines[0] == "id,name,category,cost,margin_pct,final_price"
        assert len([line for line in lines if line]) == 4  # header + 3 filas
        alpha_row = lines[1].split(",")
        assert alpha_row[1] == "Alpha"
        assert alpha_row[2] == "Postres"
        assert alpha_row[3] == "100.00"
        assert alpha_row[4] == "50"
        assert alpha_row[5] == "238.00"
        beta_row = lines[2].split(",")
        assert beta_row[1] == "Beta"
        assert beta_row[2] == ""
        assert beta_row[3] == "200.00"
        assert beta_row[5] == "339.99"
        gamma_row = lines[3].split(",")
        assert gamma_row[1] == "Gamma"
        assert gamma_row[3] == "300.00"
        assert gamma_row[5] == "396.66"

    async def test_csv_cost_is_pre_rounding_and_final_is_rounded(self, client):
        """Con rounding integer: `cost` NUNCA se redondea; `final_price`
        si."""
        token = await _admin(client)
        await _seed_price_list(client, token)
        await _set_settings(client, token, rounding_mode="integer")
        text = (
            await client.get(
                "/api/v1/calc/products/price-list/export", headers=_auth(token)
            )
        ).text
        lines = text.split("\n")
        # Beta: cost 200.00 (intacto), final 339.99 -> 340.
        beta_row = lines[2].split(",")
        assert beta_row[3] == "200.00"
        assert beta_row[5] == "340"

    async def test_csv_quotes_name_with_comma(self, client):
        token = await _admin(client)
        await _seed_price_list(client, token)
        material = (
            await client.get(
                "/api/v1/calc/materials",
                params={"q": "Mantequilla"},
                headers=_auth(token),
            )
        ).json()["items"][0]
        await _create_product(
            client,
            token,
            name="Pie, de Limon",
            status="active",
            materials=[{"material_id": material["id"], "quantity_used": "1"}],
        )
        text = (
            await client.get(
                "/api/v1/calc/products/price-list/export", headers=_auth(token)
            )
        ).text
        assert '"Pie, de Limon"' in text

    async def test_csv_headers_content_type_and_disposition(self, client):
        token = await _admin(client)
        await _seed_price_list(client, token)
        response = await client.get(
            "/api/v1/calc/products/price-list/export", headers=_auth(token)
        )
        assert response.headers["content-type"].startswith("text/csv")
        assert "charset=utf-8" in response.headers["content-type"]
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="lista_precios.csv"'
        )
        # line terminator \n (no CRLF).
        assert b"\r\n" not in response.content

    async def test_export_respects_filters_without_pagination(self, client):
        token = await _admin(client)
        seed = await _seed_price_list(client, token)
        text = (
            await client.get(
                "/api/v1/calc/products/price-list/export",
                params={"q": "torta", "category_id": seed["cat"]["id"]},
                headers=_auth(token),
            )
        ).text
        lines = [line for line in text.split("\n") if line]
        assert len(lines) == 2  # header + solo Gamma
        assert lines[1].split(",")[1] == "Gamma"

    async def test_export_empty_set_returns_header_only(self, client):
        token = await _admin(client)
        text = (
            await client.get(
                "/api/v1/calc/products/price-list/export",
                params={"q": "inexistente"},
                headers=_auth(token),
            )
        ).text
        lines = [line for line in text.split("\n") if line]
        assert lines == ["id,name,category,cost,margin_pct,final_price"]

    async def test_export_neutralizes_formula_prefix_in_name(self, client):
        token = await _admin(client)
        await _create_product(client, token, name="=1+1", status="active")
        text = (
            await client.get(
                "/api/v1/calc/products/price-list/export", headers=_auth(token)
            )
        ).text
        lines = [line for line in text.split(chr(10)) if line]
        assert lines[1].split(",")[1] == "'=1+1"

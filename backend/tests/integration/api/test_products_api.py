import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from main import app
from data.models import Base
from data.accent import accent_fold
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
    name="Torta de Limón",
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


# --- Auth / RBAC -----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_requires_authentication(client):
    response = await client.get("/api/v1/products")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_allows_customer(client):
    token = await _customer_token(client)
    response = await client.get(
        "/api/v1/products", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_create_requires_admin(client):
    token = await _customer_token(client)
    response = await client.post(
        "/api/v1/products",
        json={"name": "Torta", "category": "Tortas", "recipe": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_update_or_delete(client):
    admin_headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, admin_headers)
    flour = await _create_ingredient(client, admin_headers, "Harina")
    product = await _create_product(
        client,
        admin_headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    customer_headers = {"Authorization": f"Bearer {await _customer_token(client)}"}
    patch = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Torta Hackeada"},
        headers=customer_headers,
    )
    assert patch.status_code == 403
    delete = await client.delete(
        f"/api/v1/products/{product['id']}", headers=customer_headers
    )
    assert delete.status_code == 403


# --- Create ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_201_with_derived_price(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")

    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    # Default de settings: prep 30, servings 6, dificultad simple (RF-P4-01)
    assert product["prep_time_min"] == 30
    assert product["servings"] == 6
    assert product["difficulty"] == "simple"
    assert product["complete"] is True
    assert product["missing_ingredients"] == []
    # 250 g @ 2800/kg = 700 + mano 75 = 775; margen 100% → 1550; paso 5 → 1550
    assert product["price"]["final"] == 155000
    assert product["price"]["rounded"] == 155000
    assert product["price_per_serving"] == 25833
    line = product["recipe"][0]
    assert line["ingredient_name"] == "Harina"
    assert line["purchase_unit"] == "kg"
    assert line["missing"] is False
    assert line["line_cost"] == 70000
    # Money como int de centavos / Qty como str en la response
    assert isinstance(product["price"]["materials"], int)


@pytest.mark.asyncio
async def test_create_422_validation_errors(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    flour = await _create_ingredient(client, headers, "Harina")
    short_name = await client.post(
        "/api/v1/products",
        json={
            "name": "T",
            "category": "Tortas",
            "recipe": [{"ingredient_id": flour["id"], "qty": 1, "unit": "g"}],
        },
        headers=headers,
    )
    assert short_name.status_code == 422
    empty_recipe = await client.post(
        "/api/v1/products",
        json={"name": "Torta", "category": "Tortas", "recipe": []},
        headers=headers,
    )
    assert empty_recipe.status_code == 422


@pytest.mark.asyncio
async def test_create_400_unknown_ingredient(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta",
            "category": "Tortas",
            "recipe": [{"ingredient_id": "no-existe", "qty": 100, "unit": "g"}],
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "Insumo desconocido" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_400_incompatible_units(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    # El insumo se compra en unidades; la receta pide gramos → 400,
    # como /pricing/preview.
    huevos = await _create_ingredient(
        client, headers, "Huevos", unit="unidad", price=9000
    )
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta",
            "category": "Tortas",
            "recipe": [{"ingredient_id": huevos["id"], "qty": 250, "unit": "g"}],
        },
        headers=headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_400_duplicate_ingredient(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    flour = await _create_ingredient(client, headers, "Harina")
    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Torta",
            "category": "Tortas",
            "recipe": [
                {"ingredient_id": flour["id"], "qty": 100, "unit": "g"},
                {"ingredient_id": flour["id"], "qty": 200, "unit": "g"},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "duplicado" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_incomplete_product_when_price_zero(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    # Precio 0 = "sin precio" (decision de negocio Fase 5).
    harina = await _create_ingredient(
        client, headers, "Harina Sin Precio", price=0
    )
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": harina["id"], "qty": 250, "unit": "g"}],
    )
    assert product["complete"] is False
    assert product["price"] is None
    assert product["price_per_serving"] is None
    assert product["missing_ingredients"] == ["Harina Sin Precio"]
    assert product["recipe"][0]["missing"] is True
    assert product["recipe"][0]["line_cost"] is None


# --- List ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_search_insensitive_to_accents_and_case(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    await _create_product(
        client,
        headers,
        name="Torta de Limón",
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    # RF-P3-01: "limon" encuentra "Limón".
    response = await client.get(
        "/api/v1/products",
        params={"q": "limon"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Torta de Limón"
    # Mayúsculas tambien.
    response = await client.get(
        "/api/v1/products",
        params={"q": "TORTA"},
        headers=headers,
    )
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_category_filter_and_distinct_categories(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    await _create_product(
        client,
        headers,
        name="Torta",
        category="Tortas",
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    limonada = await _create_ingredient(
        client, headers, "Limon", unit="unidad", price=10000
    )
    await _create_product(
        client,
        headers,
        name="Limonada",
        category="Bebidas",
        recipe=[{"ingredient_id": limonada["id"], "qty": 2, "unit": "unidad"}],
    )
    body = (
        await client.get(
            "/api/v1/products",
            params={"category": "Bebidas"},
            headers=headers,
        )
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Limonada"
    # Chips del P3: derivadas de los productos activos.
    all_body = (
        await client.get(
            "/api/v1/products",
            headers=headers,
        )
    ).json()
    assert all_body["categories"] == ["Bebidas", "Tortas"]


@pytest.mark.asyncio
async def test_list_pagination(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    for index in range(25):
        await _create_product(
            client,
            headers,
            name=f"Producto {index:02d}",
            recipe=[{"ingredient_id": flour["id"], "qty": 100, "unit": "g"}],
        )
    page1 = (
        await client.get(
            "/api/v1/products",
            params={"page": 1, "page_size": 20},
            headers=headers,
        )
    ).json()
    assert page1["total"] == 25
    assert len(page1["items"]) == 20
    page2 = (
        await client.get(
            "/api/v1/products",
            params={"page": 2, "page_size": 20},
            headers=headers,
        )
    ).json()
    assert len(page2["items"]) == 5


@pytest.mark.asyncio
async def test_list_price_null_for_incomplete_product(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    sin_precio = await _create_ingredient(
        client, headers, "Insumo Sin Precio", price=0
    )
    await _create_product(
        client,
        headers,
        name="Incompleto",
        recipe=[{"ingredient_id": sin_precio["id"], "qty": 100, "unit": "g"}],
    )
    body = (
        await client.get(
            "/api/v1/products",
            headers=headers,
        )
    ).json()
    item = body["items"][0]
    assert item["complete"] is False
    assert item["price_final"] is None
    assert item["price_per_serving"] is None


# --- Detail ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_200_full_breakdown(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    huevos = await _create_ingredient(
        client, headers, "Huevos", unit="unidad", price=9000
    )
    product = await _create_product(
        client,
        headers,
        recipe=[
            {"ingredient_id": flour["id"], "qty": 250, "unit": "g"},
            {"ingredient_id": huevos["id"], "qty": 4, "unit": "unidad"},
        ],
    )
    response = await client.get(
        f"/api/v1/products/{product['id']}",
        headers=headers,
    )
    assert response.status_code == 200
    detail = response.json()
    # 700 + 360 = 1060 + mano 75 = 1135; margen 100% → 2270 (paso 5 exacto)
    assert detail["price"]["materials"] == 106000
    assert detail["price"]["waste"] == 0
    assert detail["price"]["materials_con_merma"] == 106000
    assert detail["price"]["labor"] == 7500
    assert detail["price"]["gas"] == 0
    assert detail["price"]["base"] == 113500
    assert detail["price"]["final"] == 227000
    assert detail["price"]["rounded"] == 227000
    assert detail["price_per_serving"] == 37833


@pytest.mark.asyncio
async def test_detail_404(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await client.get(
        "/api/v1/products/no-existe",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detail_recipe_shows_missing_ingredients(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    sin_precio = await _create_ingredient(
        client, headers, "Azucar Sin Precio", price=0
    )
    product = await _create_product(
        client,
        headers,
        recipe=[
            {"ingredient_id": flour["id"], "qty": 250, "unit": "g"},
            {"ingredient_id": sin_precio["id"], "qty": 100, "unit": "g"},
        ],
    )
    detail = (
        await client.get(
            f"/api/v1/products/{product['id']}",
            headers=headers,
        )
    ).json()
    assert detail["complete"] is False
    assert detail["missing_ingredients"] == ["Azucar Sin Precio"]
    by_id = {line["ingredient_id"]: line for line in detail["recipe"]}
    assert by_id[flour["id"]]["missing"] is False
    assert by_id[flour["id"]]["line_cost"] == 70000
    assert by_id[sin_precio["id"]]["missing"] is True
    assert by_id[sin_precio["id"]]["line_cost"] is None


# --- Update ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_200_rename_and_replace_recipe(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "Torta Grande", "servings": 12},
        headers=headers,
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["name"] == "Torta Grande"
    assert detail["servings"] == 12
    # 1550 / 12 = 129.1666 → 12917
    assert detail["price_per_serving"] == 12917


@pytest.mark.asyncio
async def test_update_partial_keeps_other_fields(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        name="Torta Original",
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    detail = (
        await client.patch(
            f"/api/v1/products/{product['id']}",
            json={"category": "Postres"},
            headers=headers,
        )
    ).json()
    assert detail["category"] == "Postres"
    assert detail["name"] == "Torta Original"
    assert detail["recipe"][0]["ingredient_id"] == flour["id"]


@pytest.mark.asyncio
async def test_update_404(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await client.patch(
        "/api/v1/products/no-existe",
        json={"name": "Cualquiera"},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_400_incompatible_units(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    huevos = await _create_ingredient(
        client, headers, "Huevos", unit="unidad", price=9000
    )
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    response = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={
            "recipe": [{"ingredient_id": huevos["id"], "qty": 250, "unit": "g"}]
        },
        headers=headers,
    )
    assert response.status_code == 400


# --- Delete ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_204_then_invisible(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    response = await client.delete(
        f"/api/v1/products/{product['id']}",
        headers=headers,
    )
    assert response.status_code == 204
    detail = await client.get(
        f"/api/v1/products/{product['id']}",
        headers=headers,
    )
    assert detail.status_code == 404
    listing = await client.get(
        "/api/v1/products",
        headers=headers,
    )
    assert listing.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_404_unknown(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    response = await client.delete(
        "/api/v1/products/no-existe",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_with_historical_orders_soft_deletes_and_reports(
    client, db_session
):
    """RF-P4-08: con pedidos históricos NO se bloquea. Soft delete siempre;
    la response informa el impacto (200 + impacted_orders) y el producto
    desaparece del catálogo."""
    from api.v1.products.dependencies import get_product_repository
    from data.repositories.sql_product_repository import SQLProductRepository

    class _OrdersStubRepository(SQLProductRepository):
        async def count_orders(self, product_id: str) -> int:
            return 3

    async def override_repo():
        yield _OrdersStubRepository(db_session)

    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )

    app.dependency_overrides[get_product_repository] = override_repo
    try:
        response = await client.delete(
            f"/api/v1/products/{product['id']}",
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_product_repository, None)

    assert response.status_code == 200
    assert response.json()["impacted_orders"] == 3
    detail = await client.get(
        f"/api/v1/products/{product['id']}",
        headers=headers,
    )
    assert detail.status_code == 404


# --- Derivacion en lectura (RF-P3-04) ---------------------------------------


@pytest.mark.asyncio
async def test_price_follows_ingredient_price_changes(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    product = await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    # 700 + 75 = 775 → 1550
    assert product["price"]["rounded"] == 155000
    # El precio del insumo sube a 4000/kg → 1000 + 75 = 1075 → 2150.
    patch = await client.patch(
        f"/api/v1/ingredients/{flour['id']}",
        json={"price_per_unit": 400000},
        headers=headers,
    )
    assert patch.status_code == 200
    detail = (
        await client.get(
            f"/api/v1/products/{product['id']}",
            headers=headers,
        )
    ).json()
    assert detail["price"]["materials"] == 100000
    assert detail["price"]["rounded"] == 215000


# --- Efecto colateral: count_active_recipes ahora es real -------------------


@pytest.mark.asyncio
async def test_ingredient_delete_409_when_used_in_product(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    await _set_settings(client, headers)
    flour = await _create_ingredient(client, headers, "Harina")
    await _create_product(
        client,
        headers,
        recipe=[{"ingredient_id": flour["id"], "qty": 250, "unit": "g"}],
    )
    response = await client.delete(
        f"/api/v1/ingredients/{flour['id']}",
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["impacted_recipes"] == 1


@pytest.mark.asyncio
async def test_ingredient_delete_204_when_unused(client):
    headers = {"Authorization": f"Bearer {await _admin_token(client)}"}
    flour = await _create_ingredient(client, headers, "Manteca")
    response = await client.delete(
        f"/api/v1/ingredients/{flour['id']}",
        headers=headers,
    )
    assert response.status_code == 204

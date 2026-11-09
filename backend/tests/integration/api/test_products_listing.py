import uuid

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.products.dependencies import get_product_repository
from api.v1.settings.dependencies import get_settings_repository
from data.db import get_db
from data.models import (
    BusinessSettingsORM,
    IngredientORM,
    ProductORM,
    RecipeItemORM,
)
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.repositories.sql_product_repository import SQLProductRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole
from main import app

_STORE_ROW_KEYS = {
    "id",
    "name",
    "category",
    "description",
    "image_url",
    "price",
    "price_per_serving",
    "complete",
}

_LEAKY_KEYS = {
    "price_per_unit",
    "unit",
    "status",
    "stock_qty",
    "base",
    "materials",
    "labor",
    "margin_pct",
    "breakdown",
}


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

    user_repo = SQLUserRepository(db_session)
    await user_repo.save(User(email="admin@example.com", role=UserRole.ADMIN))
    await user_repo.save(User(email="negocio@example.com", role=UserRole.NEGOCIO))
    await user_repo.save(User(email="cliente@example.com", role=UserRole.CUSTOMER))

    db_session.add(
        BusinessSettingsORM(
            hourly_rate="0.01",
            margin_pct="25",
            round_step="0.01",
            gas_pct="0",
            waste_pct="0",
            consumer_markup_pct="40",
            include_labor=False,
            include_gas=False,
            include_waste=False,
            default_prep_minutes=0,
            default_servings=1,
            default_difficulty="simple",
            business_name="",
            footer_text="",
        )
    )
    db_session.add(
        IngredientORM(id=str(uuid.uuid4()), name="Harina 0000", unit="kg", price_per_unit="10.00", stock_qty="10")
    )
    db_session.add(
        IngredientORM(id=str(uuid.uuid4()), name="Azúcar refinada", unit="kg", price_per_unit="20.00", stock_qty="10")
    )
    db_session.add(
        IngredientORM(id=str(uuid.uuid4()), name="Manteca sin sal", unit="kg", price_per_unit="15.00", stock_qty="10")
    )
    await db_session.commit()

    ingredient_ids = {
        orm.name: orm.id
        for orm in (await db_session.execute(select(IngredientORM))).scalars().all()
    }

    await _add_product(db_session, "Pan de campo", "Pan", 4, True, [
        (ingredient_ids["Harina 0000"], "1", "kg"),
    ])
    await _add_product(db_session, "Muffin de chocolate", "Muffins", 6, True, [
        (ingredient_ids["Manteca sin sal"], "1", "kg"),
    ])
    await _add_product(db_session, "Café con leche", "Bebidas", 2, True, [
        (ingredient_ids["Azúcar refinada"], "1", "kg"),
    ])
    await _add_product(db_session, "Torta oculta", "Tortas", 4, False, [
        (ingredient_ids["Harina 0000"], "1", "kg"),
    ])
    await _add_product(db_session, "Torta incompleta", "Tortas", 4, True, [
        (str(uuid.uuid4()), "1", "kg"),
    ])

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _add_product(
    db_session,
    name: str,
    category: str,
    servings: int,
    available: bool,
    recipe: list[tuple[str, str, str]],
) -> None:
    product = ProductORM(
        id=str(uuid.uuid4()),
        name=name,
        category=category,
        description="",
        prep_time_min=0,
        servings=servings,
        difficulty="simple",
        available=available,
    )
    product.recipe_items = [
        RecipeItemORM(
            id=str(uuid.uuid4()),
            product_id=product.id,
            ingredient_id=ingredient_id,
            qty=qty,
            unit=unit,
            position=position,
        )
        for position, (ingredient_id, qty, unit) in enumerate(recipe)
    ]
    db_session.add(product)
    await db_session.commit()


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.cookies["auth_token"]


async def _list(
    client: AsyncClient,
    token: str | None = None,
    audience: str | None = "revendedores",
    **params,
):
    query = {**params}
    if audience is not None:
        query["audience"] = audience
    headers = {}
    if token is not None:
        headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(
        "/api/v1/products", params=query, headers=headers
    )
    return response


def _by_name(data: dict) -> dict[str, dict]:
    return {row["name"]: row for row in data["products"]}


@pytest.mark.asyncio
async def test_requires_auth(client):
    response = await client.get("/api/v1/products", params={"audience": "revendedores"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_access_both_audiences(client):
    token = await _token_for(client, "admin@example.com")
    r_rev = await _list(client, token, "revendedores")
    r_cons = await _list(client, token, "consumidor_final")
    assert r_rev.status_code == 200
    assert r_cons.status_code == 200
    assert r_rev.json()["audience"] == "revendedores"
    assert r_cons.json()["audience"] == "consumidor_final"


@pytest.mark.asyncio
async def test_admin_revendedores_sees_engine_prices(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores")
    assert r.status_code == 200
    rows = _by_name(r.json())
    assert Decimal(rows["Pan de campo"]["price"]) == Decimal("12.50")
    assert Decimal(rows["Pan de campo"]["price_per_serving"]) == Decimal("3.13")
    assert Decimal(rows["Muffin de chocolate"]["price"]) == Decimal("18.75")
    assert Decimal(rows["Muffin de chocolate"]["price_per_serving"]) == Decimal("3.13")
    assert Decimal(rows["Café con leche"]["price"]) == Decimal("25.00")
    assert Decimal(rows["Café con leche"]["price_per_serving"]) == Decimal("12.50")


@pytest.mark.asyncio
async def test_admin_consumidor_final_applies_markup(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "consumidor_final")
    assert r.status_code == 200
    rows = _by_name(r.json())
    assert Decimal(rows["Pan de campo"]["price"]) == Decimal("17.50")
    assert Decimal(rows["Muffin de chocolate"]["price"]) == Decimal("26.25")
    assert Decimal(rows["Café con leche"]["price"]) == Decimal("35.00")


@pytest.mark.asyncio
async def test_negocio_revendedores_200(client):
    token = await _token_for(client, "negocio@example.com")
    r = await _list(client, token, "revendedores")
    assert r.status_code == 200
    assert r.json()["audience"] == "revendedores"


@pytest.mark.asyncio
async def test_negocio_consumidor_final_403(client):
    token = await _token_for(client, "negocio@example.com")
    r = await _list(client, token, "consumidor_final")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cliente_revendedores_403(client):
    token = await _token_for(client, "cliente@example.com")
    r = await _list(client, token, "revendedores")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cliente_consumidor_final_200_with_prices(client):
    token = await _token_for(client, "cliente@example.com")
    r = await _list(client, token, "consumidor_final")
    assert r.status_code == 200
    rows = _by_name(r.json())
    assert Decimal(rows["Pan de campo"]["price"]) == Decimal("17.50")


@pytest.mark.asyncio
async def test_invalid_audience_422(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "inválida")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_audience_shape(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"audience", "products", "total", "categories"}
    assert data["total"] == 3
    assert data["categories"] == ["Bebidas", "Muffins", "Pan"]
    for row in data["products"]:
        assert set(row.keys()) == _STORE_ROW_KEYS
        assert row["complete"] is True
        assert row["image_url"] is None


@pytest.mark.asyncio
async def test_hidden_and_incomplete_products_not_exposed(client):
    admin_token = await _token_for(client, "admin@example.com")
    cliente_token = await _token_for(client, "cliente@example.com")
    combos = [
        (admin_token, "revendedores"),
        (admin_token, "consumidor_final"),
        (cliente_token, "consumidor_final"),
        (await _token_for(client, "negocio@example.com"), "revendedores"),
    ]
    for token, audience in combos:
        r = await _list(client, token, audience)
        assert r.status_code == 200
        names = [row["name"] for row in r.json()["products"]]
        assert "Torta oculta" not in names
        assert "Torta incompleta" not in names


@pytest.mark.asyncio
async def test_q_filters_by_name(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="pan")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [row["name"] for row in data["products"]] == ["Pan de campo"]


@pytest.mark.asyncio
async def test_q_is_accent_insensitive(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="cafe")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [row["name"] for row in data["products"]] == ["Café con leche"]


@pytest.mark.asyncio
async def test_q_no_match_returns_empty(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="zzz")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["products"] == []
    assert data["categories"] == []


@pytest.mark.asyncio
async def test_q_percent_is_literal(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="%")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_underscore_is_literal(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="_")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_backslash_is_literal(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="\\")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_mixed_special_is_literal(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="a%b_c")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_q_rejects_null_byte(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="harina\x00x")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_rejects_bidirectional_control(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="pan\u202evolver")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_q_rejects_oversized_and_whitespace(client):
    token = await _token_for(client, "admin@example.com")
    r_long = await _list(client, token, "revendedores", q="a" * 121)
    assert r_long.status_code == 422
    r_ws = await _list(client, token, "revendedores", q="   ")
    assert r_ws.status_code == 422


@pytest.mark.asyncio
async def test_q_with_pagination_returns_slice_and_full_total(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "revendedores", q="a", page_size=2)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["products"]) == 2


@pytest.mark.asyncio
async def test_admin_pagination_slice_and_total(client):
    token = await _token_for(client, "admin@example.com")
    r1 = await _list(client, token, "revendedores", page_size=2, page=1)
    r2 = await _list(client, token, "revendedores", page_size=2, page=2)
    assert r1.status_code == 200
    assert r2.status_code == 200
    p1 = r1.json()
    p2 = r2.json()
    assert p1["total"] == 3
    assert p2["total"] == 3
    assert len(p1["products"]) == 2
    assert len(p2["products"]) == 1
    ids_p1 = {row["id"] for row in p1["products"]}
    ids_p2 = {row["id"] for row in p2["products"]}
    assert ids_p1.isdisjoint(ids_p2)
    assert len(ids_p1 | ids_p2) == 3

    r_big = await _list(client, token, "revendedores", page_size=501)
    assert r_big.status_code == 422


@pytest.mark.asyncio
async def test_no_cost_data_leaks_in_store_rows(client):
    token = await _token_for(client, "admin@example.com")
    r = await _list(client, token, "consumidor_final")
    assert r.status_code == 200
    for row in r.json()["products"]:
        assert not (_LEAKY_KEYS & set(row.keys()))


_STORE_DETAIL_KEYS = {
    "id",
    "name",
    "category",
    "description",
    "image_url",
    "price",
    "servings",
    "prep_time_min",
}


async def _product_id(db_session, name: str) -> str:
    return (
        await db_session.execute(select(ProductORM).where(ProductORM.name == name))
    ).scalar_one().id


async def _detail(
    client: AsyncClient,
    product_id: str,
    token: str | None = None,
    audience: str | None = None,
):
    params = {} if audience is None else {"audience": audience}
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    return await client.get(
        f"/api/v1/products/{product_id}", params=params, headers=headers
    )


@pytest.mark.asyncio
async def test_store_detail_cliente_consumidor_final_shape_and_price(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, product_id, token, "consumidor_final")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == _STORE_DETAIL_KEYS
    assert body["name"] == "Pan de campo"
    assert body["category"] == "Pan"
    assert body["servings"] == 4
    assert Decimal(body["price"]) == Decimal("17.50")
    assert not (_LEAKY_KEYS & set(body))
    assert "recipe" not in body
    assert "missing_ingredients" not in body
    assert "available" not in body


@pytest.mark.asyncio
async def test_store_detail_negocio_revendedores_base_price(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "negocio@example.com")
    r = await _detail(client, product_id, token, "revendedores")
    assert r.status_code == 200
    assert Decimal(r.json()["price"]) == Decimal("12.50")


@pytest.mark.asyncio
async def test_store_detail_negocio_consumidor_final_403(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "negocio@example.com")
    r = await _detail(client, product_id, token, "consumidor_final")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_store_detail_cliente_revendedores_403(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, product_id, token, "revendedores")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_store_detail_requires_auth(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    r = await _detail(client, product_id, None, "consumidor_final")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_store_detail_portal_role_without_audience_403(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, product_id, token, None)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_store_detail_hidden_product_404(client, db_session):
    product_id = await _product_id(db_session, "Torta oculta")
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, product_id, token, "consumidor_final")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_store_detail_incomplete_product_404(client, db_session):
    product_id = await _product_id(db_session, "Torta incompleta")
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, product_id, token, "consumidor_final")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_store_detail_unknown_product_404(client):
    token = await _token_for(client, "cliente@example.com")
    r = await _detail(client, str(uuid.uuid4()), token, "consumidor_final")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_store_detail_admin_with_audience_gets_store_shape(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "admin@example.com")
    r = await _detail(client, product_id, token, "consumidor_final")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == _STORE_DETAIL_KEYS
    assert Decimal(body["price"]) == Decimal("17.50")


@pytest.mark.asyncio
async def test_store_detail_admin_without_audience_keeps_admin_contract(client, db_session):
    product_id = await _product_id(db_session, "Pan de campo")
    token = await _token_for(client, "admin@example.com")
    r = await _detail(client, product_id, token, None)
    assert r.status_code == 200
    body = r.json()
    assert "price" in body and "base" in body["price"]
    assert body["recipe"]
    assert "missing_ingredients" in body
    assert "available" in body

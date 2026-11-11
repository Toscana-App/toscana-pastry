import uuid

import csv
import uuid
from decimal import Decimal
from io import StringIO

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
            hourly_rate="100",
            margin_pct="25",
            round_step="0.01",
            gas_pct="0",
            waste_pct="0",
            consumer_markup_pct="40",
            include_labor=True,
            include_gas=False,
            include_waste=False,
            default_prep_minutes=0,
            default_servings=6,
            default_difficulty="simple",
            business_name="",
            footer_text="",
        )
    )
    db_session.add(
        IngredientORM(id=str(uuid.uuid4()), name="Harina 0000", unit="kg", price_per_unit="10.00", stock_qty="10")
    )
    db_session.add(
        IngredientORM(id=str(uuid.uuid4()), name="Azúcar refinada", unit="kg", price_per_unit="5.00", stock_qty="10")
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
    await _add_product(db_session, "Torta de almendras", "Tortas", 8, True, [
        (ingredient_ids["Harina 0000"], "1", "kg"),
        (ingredient_ids["Azúcar refinada"], "1", "kg"),
    ])
    await _add_product(db_session, "Brownie oculto", "Postres", 2, False, [
        (ingredient_ids["Azúcar refinada"], "1", "kg"),
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


def _csv_rows(r) -> list[dict]:
    return list(csv.DictReader(StringIO(r.content.decode("utf-8"))))


def _csv_price(rows: list[dict], name: str) -> Decimal:
    return Decimal([row["price"] for row in rows if row["name"] == name][0].lstrip("$"))


@pytest.mark.asyncio
async def test_csv_header_and_rows(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8")
    assert text.splitlines()[0] == "name,category,price"
    rows = _csv_rows(r)
    assert len(rows) == 3
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"Pan de campo", "Muffin de chocolate", "Torta de almendras"}
    assert by_name["Pan de campo"]["category"] == "Pan"
    assert by_name["Muffin de chocolate"]["category"] == "Muffins"
    assert by_name["Torta de almendras"]["category"] == "Tortas"


@pytest.mark.asyncio
async def test_csv_filename_header(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "pricelist_revendedores.csv" in r.headers["content-disposition"]
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "pricelist_consumidor_final.csv" in r.headers["content-disposition"]


@pytest.mark.asyncio
async def test_csv_revendedores_uses_base(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    rows = _csv_rows(r)
    assert _csv_price(rows, "Pan de campo") == Decimal("12.50")
    assert _csv_price(rows, "Muffin de chocolate") == Decimal("18.75")
    assert _csv_price(rows, "Torta de almendras") == Decimal("18.75")


@pytest.mark.asyncio
async def test_csv_consumidor_applies_markup(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    rows = _csv_rows(r)
    assert _csv_price(rows, "Pan de campo") == Decimal("17.50")
    assert _csv_price(rows, "Muffin de chocolate") == Decimal("26.25")
    assert _csv_price(rows, "Torta de almendras") == Decimal("26.25")


@pytest.mark.asyncio
async def test_csv_excludes_hidden_and_incomplete(client):
    token = await _token_for(client, "admin@example.com")
    for audience in ("revendedores", "consumidor_final"):
        r = await client.get(
            "/api/v1/products/pricelist/csv",
            params={"audience": audience},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        names = {row["name"] for row in _csv_rows(r)}
        assert "Brownie oculto" not in names
        assert "Torta incompleta" not in names


@pytest.mark.asyncio
async def test_pdf_returns_pdf_bytes(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert "attachment" in r.headers["content-disposition"]
    assert "pricelist_consumidor_final.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_pdf_rows_carry_category_and_price(client, pdf_fake):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    call = pdf_fake.calls[-1]
    assert call[0] == "render_pricelist"
    rows, label = call[1]
    assert label == "Consumidor final"
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"Pan de campo", "Muffin de chocolate", "Torta de almendras"}
    assert by_name["Pan de campo"]["category"] == "Pan"
    assert by_name["Pan de campo"]["price"] == "$17,50"
    assert by_name["Muffin de chocolate"]["category"] == "Muffins"
    assert by_name["Muffin de chocolate"]["price"] == "$26,25"
    assert by_name["Torta de almendras"]["price"] == "$26,25"


@pytest.mark.asyncio
async def test_pdf_revendedores_label(client, pdf_fake):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    call = pdf_fake.calls[-1]
    rows, label = call[1]
    assert label == "Revendedores"
    by_name = {row["name"]: row for row in rows}
    assert by_name["Pan de campo"]["price"] == "$12,50"


@pytest.mark.asyncio
async def test_csv_neutralizes_formula_injection(client, db_session):
    token = await _token_for(client, "admin@example.com")
    ingredient_id = (
        await db_session.execute(
            select(IngredientORM).where(IngredientORM.name == "Harina 0000")
        )
    ).scalar_one().id
    for evil in ("=HYPERLINK(1)", "+cmd", "-rm", "@alert", "ok"):
        await _add_product(db_session, evil, "Evil", 1, True, [
            (ingredient_id, "1", "kg"),
        ])
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert "'=HYPERLINK(1)" in text
    assert "'+cmd" in text
    assert "'-rm" in text
    assert "'@alert" in text
    assert "\nok," in text


@pytest.mark.asyncio
async def test_csv_escapes_commas_and_quotes(client, db_session):
    token = await _token_for(client, "admin@example.com")
    ingredient_id = (
        await db_session.execute(
            select(IngredientORM).where(IngredientORM.name == "Harina 0000")
        )
    ).scalar_one().id
    tricky = ['Chocolate "premium"', "Harina, tipo 000", 'Miel "orgánica", 1kg']
    for name in tricky:
        await _add_product(db_session, name, "General", 1, True, [
            (ingredient_id, "1", "kg"),
        ])
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    parsed = list(csv.reader(StringIO(r.content.decode("utf-8"))))
    names = {row[0] for row in parsed[1:]}
    for name in tricky:
        assert name in names


@pytest.mark.asyncio
async def test_admin_csv_and_pdf_both_audiences(client):
    token = await _token_for(client, "admin@example.com")
    for audience in ("revendedores", "consumidor_final"):
        r = await client.get(
            "/api/v1/products/pricelist/csv",
            params={"audience": audience},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        r = await client.get(
            "/api/v1/products/pricelist/pdf",
            params={"audience": audience},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_negocio_csv_revendedores_ok(client):
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(_csv_rows(r)) == 3


@pytest.mark.asyncio
async def test_negocio_pdf_revendedores_ok(client):
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_negocio_csv_consumidor_final_403(client):
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_negocio_pdf_consumidor_final_403(client):
    token = await _token_for(client, "negocio@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cliente_csv_consumidor_final_ok(client):
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(_csv_rows(r)) == 3


@pytest.mark.asyncio
async def test_cliente_pdf_consumidor_final_ok(client):
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "consumidor_final"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_cliente_csv_revendedores_403(client):
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cliente_pdf_revendedores_403(client):
    token = await _token_for(client, "cliente@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "revendedores"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_invalid_audience_csv_422(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "público"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_audience_pdf_422(client):
    token = await _token_for(client, "admin@example.com")
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "público"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_csv_401(client):
    r = await client.get(
        "/api/v1/products/pricelist/csv",
        params={"audience": "revendedores"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_pdf_401(client):
    r = await client.get(
        "/api/v1/products/pricelist/pdf",
        params={"audience": "revendedores"},
    )
    assert r.status_code == 401

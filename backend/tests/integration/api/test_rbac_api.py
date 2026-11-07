import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.v1.auth.dependencies import get_user_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
from api.v1.settings.dependencies import get_settings_repository
from data.db import get_db
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
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


@pytest.mark.asyncio
async def test_admin_users_requires_authentication(client):
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_users_rejects_invalid_token(client):
    response = await client.get(
        "/api/v1/admin/users", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_users_forbidden_for_customer(client):
    token = await _token_for(client, "customer@example.com")
    response = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_admin_users_allowed_for_admin(client, db_session):
    await SQLUserRepository(db_session).save(
        User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)
    )

    token = await _token_for(client, "admin@example.com")
    response = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["users"][0]["email"] == "admin@example.com"
    assert body["users"][0]["role"] == "admin"


# --- Escritura de configuración, catálogo y pricing: sólo ADMIN ------------

_SETTINGS_PAYLOAD = {
    "hourly_rate": 300000,
    "margin_pct": "30",
    "round_step": 10000,
    "include_labor": True,
    "include_gas": True,
    "gas_pct": "3",
    "include_waste": True,
    "waste_pct": "3",
    "urgent_surcharge_pct": "20",
    "default_prep_minutes": 30,
    "default_servings": 6,
    "default_difficulty": "simple",
}

_INGREDIENT_PAYLOAD = {
    "name": "Harina 0000",
    "unit": "kg",
    "price_per_unit": 280000,
    "stock_qty": "5",
    "low_stock_threshold": "1",
}

_PREVIEW_PAYLOAD = {
    "line_items": [
        {
            "qty": "250",
            "unit": "g",
            "price_per_purchase_unit": 280000,
            "purchase_unit": "kg",
        }
    ],
    "prep_minutes": 30,
}


@pytest.mark.asyncio
async def test_settings_write_forbidden_for_customer(client):
    token = await _token_for(client, "customer@example.com")
    response = await client.put(
        "/api/v1/tenant/settings",
        json=_SETTINGS_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_settings_read_allowed_for_customer(client):
    # La lectura de la config no se restringe por rol (spec: autenticado).
    token = await _token_for(client, "customer@example.com")
    response = await client.get(
        "/api/v1/tenant/settings", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_settings_write_allowed_for_admin(client, db_session):
    await SQLUserRepository(db_session).save(
        User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)
    )
    token = await _token_for(client, "admin@example.com")
    response = await client.put(
        "/api/v1/tenant/settings",
        json=_SETTINGS_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ingredient_write_forbidden_for_customer(client):
    token = await _token_for(client, "customer@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        await client.post("/api/v1/ingredients", json=_INGREDIENT_PAYLOAD, headers=headers)
    ).status_code == 403
    assert (
        await client.post("/api/v1/ingredients/import", json={"lines": ["harina, 5, 2800"]}, headers=headers)
    ).status_code == 403
    assert (
        await client.post("/api/v1/ingredients/abc/stock", json={"delta": "1", "reason": "compra"}, headers=headers)
    ).status_code == 403
    assert (
        await client.patch("/api/v1/ingredients/abc", json={"name": "Otra"}, headers=headers)
    ).status_code == 403
    assert (await client.delete("/api/v1/ingredients/abc", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_ingredient_read_allowed_for_customer(client):
    # La lectura del catálogo no se restringe por rol (spec: autenticado).
    token = await _token_for(client, "customer@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/ingredients", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_pricing_preview_forbidden_for_customer(client):
    token = await _token_for(client, "customer@example.com")
    response = await client.post(
        "/api/v1/pricing/preview",
        json=_PREVIEW_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pricing_preview_allowed_for_admin(client, db_session):
    await SQLUserRepository(db_session).save(
        User(id="admin-1", email="admin@example.com", role=UserRole.ADMIN)
    )
    token = await _token_for(client, "admin@example.com")
    response = await client.post(
        "/api/v1/pricing/preview",
        json=_PREVIEW_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

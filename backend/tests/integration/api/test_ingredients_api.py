import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_ingredient_repository import SQLIngredientRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.ingredients.dependencies import get_ingredient_repository
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    app.dependency_overrides[get_ingredient_repository] = override_get_ingredient_repository
    # El login crea usuarios con rol CUSTOMER; las mutaciones de ingredientes
    # son de administración (RBAC), así que se siembra el ADMIN.
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


async def _token_for(client: AsyncClient, email: str = "admin@example.com") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _create_ingredient(
    client: AsyncClient,
    token: str,
    name: str = "Harina 0000",
    unit: str = "kg",
    price: int = 280000,
    stock: str = "0",
    threshold: str = "0",
    **extra,
) -> dict:
    payload = {
        "name": name,
        "unit": unit,
        "price_per_unit": price,
        "stock_qty": stock,
        "low_stock_threshold": threshold,
    }
    payload.update(extra)
    response = await client.post(
        "/api/v1/ingredients", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Auth ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingredients_requires_authentication(client):
    assert (await client.get("/api/v1/ingredients")).status_code == 401
    assert (
        await client.post("/api/v1/ingredients", json={"name": "x", "unit": "kg", "price_per_unit": 100})
    ).status_code == 401


# --- Create ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_ingredient(client):
    token = await _token_for(client)
    body = await _create_ingredient(client, token)
    assert body["name"] == "Harina 0000"
    assert body["unit"] == "kg"
    assert body["price_per_unit"] == 280000
    assert body["stock_qty"] == "0"
    assert body["status"] == "EMPTY"


@pytest.mark.asyncio
async def test_create_with_initial_stock_records_movement(client):
    token = await _token_for(client)
    body = await _create_ingredient(client, token, stock="5", threshold="2")
    assert body["status"] == "OK"
    movements = await client.get(
        f"/api/v1/ingredients/{body['id']}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.status_code == 200
    data = movements.json()
    assert data["total"] == 1
    assert data["items"][0]["qty_delta"] == "5"
    assert data["items"][0]["reason"] == "compra"
    assert data["items"][0]["ref"] == "inicial"


@pytest.mark.asyncio
async def test_create_rejects_invalid_unit(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients",
        json={"name": "Harina", "unit": "onzas", "price_per_unit": 280000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_negative_stock(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients",
        json={"name": "Harina", "unit": "kg", "price_per_unit": 280000, "stock_qty": "-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_empty_name(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients",
        json={"name": "  ", "unit": "kg", "price_per_unit": 280000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_unknown_field(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients",
        json={"name": "Harina", "unit": "kg", "price_per_unit": 280000, "brand": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# --- List / search / filter ------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(client):
    token = await _token_for(client)
    response = await client.get(
        "/api/v1/ingredients", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 50}


@pytest.mark.asyncio
async def test_list_pagination(client):
    token = await _token_for(client)
    for i in range(3):
        await _create_ingredient(client, token, name=f"Ingrediente {i}")
    page1 = (
        await client.get(
            "/api/v1/ingredients?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    page2 = (
        await client.get(
            "/api/v1/ingredients?page=2&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1


@pytest.mark.asyncio
async def test_list_search_case_insensitive(client):
    token = await _token_for(client)
    await _create_ingredient(client, token, name="Harina 0000")
    await _create_ingredient(client, token, name="Levadura", unit="g")
    response = await client.get(
        "/api/v1/ingredients?q=HARINA", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Harina 0000"


@pytest.mark.asyncio
async def test_list_search_accent_insensitive(client):
    token = await _token_for(client)
    await _create_ingredient(client, token, name="Café molido", unit="g")
    response = await client.get(
        "/api/v1/ingredients?q=cafe", headers={"Authorization": f"Bearer {token}"}
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Café molido"


@pytest.mark.asyncio
async def test_list_status_filter(client):
    token = await _token_for(client)
    await _create_ingredient(client, token, name="OK", stock="10", threshold="2")
    await _create_ingredient(client, token, name="LOW", stock="1", threshold="2")
    await _create_ingredient(client, token, name="EMPTY", stock="0")
    for status_value in ("OK", "LOW", "EMPTY"):
        response = await client.get(
            f"/api/v1/ingredients?status={status_value}",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = response.json()
        assert body["total"] == 1, status_value
        assert body["items"][0]["status"] == status_value


# --- Detail / patch ---------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredient(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token)
    response = await client.get(
        f"/api/v1/ingredients/{created['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["ingredient"]["id"] == created["id"]
    assert detail["movements"] is None


@pytest.mark.asyncio
async def test_get_ingredient_unknown_id_404(client):
    token = await _token_for(client)
    response = await client.get(
        "/api/v1/ingredients/00000000-0000-4000-8000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_partial_update(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token)
    response = await client.patch(
        f"/api/v1/ingredients/{created['id']}",
        json={"price_per_unit": 300000, "name": "Harina 0000 premium"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price_per_unit"] == 300000
    assert body["name"] == "Harina 0000 premium"
    assert body["stock_qty"] == "0"  # el stock no se toca por PATCH


@pytest.mark.asyncio
async def test_patch_empty_body_422(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token)
    response = await client.patch(
        f"/api/v1/ingredients/{created['id']}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_unknown_id_404(client):
    token = await _token_for(client)
    response = await client.patch(
        "/api/v1/ingredients/00000000-0000-4000-8000-000000000000",
        json={"name": "X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Delete (soft) -----------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_soft_deletes(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token)
    response = await client.delete(
        f"/api/v1/ingredients/{created['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    # Invisible a todo lo publico:
    assert (
        await client.get(f"/api/v1/ingredients/{created['id']}", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    listing = (
        await client.get("/api/v1/ingredients", headers={"Authorization": f"Bearer {token}"})
    ).json()
    assert listing["total"] == 0


@pytest.mark.asyncio
async def test_delete_unknown_id_404(client):
    token = await _token_for(client)
    response = await client.delete(
        "/api/v1/ingredients/00000000-0000-4000-8000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Stock adjustments -------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_adjustment_records_movement(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token, stock="10")
    response = await client.post(
        f"/api/v1/ingredients/{created['id']}/stock",
        json={"delta": "-3", "reason": "merma", "ref": "receta 7"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stock_qty"] == "7"
    assert body["movement"]["qty_delta"] == "-3"
    assert body["movement"]["reason"] == "merma"
    assert body["movement"]["ref"] == "receta 7"
    # El saldo y el historial van juntos:
    movements = (
        await client.get(
            f"/api/v1/ingredients/{created['id']}/movements",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    assert movements["total"] == 2  # inicial + merma


@pytest.mark.asyncio
async def test_stock_adjustment_negative_result_400(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token, stock="5")
    response = await client.post(
        f"/api/v1/ingredients/{created['id']}/stock",
        json={"delta": "-10", "reason": "merma"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    # El saldo queda intacto:
    detail = (
        await client.get(
            f"/api/v1/ingredients/{created['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    assert detail["ingredient"]["stock_qty"] == "5"


@pytest.mark.asyncio
async def test_stock_adjustment_zero_delta_400(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token)
    response = await client.post(
        f"/api/v1/ingredients/{created['id']}/stock",
        json={"delta": "0", "reason": "ajuste"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_stock_adjustment_unknown_ingredient_404(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients/00000000-0000-4000-8000-000000000000/stock",
        json={"delta": "1", "reason": "compra"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_movements_history_newest_first(client):
    token = await _token_for(client)
    created = await _create_ingredient(client, token, stock="4")  # movimiento inicial
    headers = {"Authorization": f"Bearer {token}"}
    for delta in ("2", "-1"):
        response = await client.post(
            f"/api/v1/ingredients/{created['id']}/stock",
            json={"delta": delta, "reason": "ajuste"},
            headers=headers,
        )
        assert response.status_code == 200
    movements = (
        await client.get(
            f"/api/v1/ingredients/{created['id']}/movements", headers=headers
        )
    ).json()
    assert movements["total"] == 3
    deltas = [item["qty_delta"] for item in movements["items"]]
    assert deltas[0] == "-1"  # el mas reciente primero
    assert Decimal(deltas[0]) + Decimal(deltas[1]) + Decimal(deltas[2]) == Decimal("5")
    # Y cuadra con el saldo final:
    detail = (
        await client.get(
            f"/api/v1/ingredients/{created['id']}", headers=headers
        )
    ).json()
    assert detail["ingredient"]["stock_qty"] == "5"


# --- Import (RF-P2-07) --------------------------------------------------------


@pytest.mark.asyncio
async def test_import_creates_valid_lines_and_reports_errors(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients/import",
        json={
            "lines": [
                "harina 0000, 5, 2800",
                "aceite, 1 L, 300",
                "mal formato",
                "azúcar, 1,5 kg, 1200",
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 3
    assert len(body["errors"]) == 1
    assert body["errors"][0]["line"] == 3
    listing = (
        await client.get("/api/v1/ingredients", headers={"Authorization": f"Bearer {token}"})
    ).json()
    assert listing["total"] == 3


@pytest.mark.asyncio
async def test_import_all_invalid_reports_every_line(client):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients/import",
        json={"lines": ["sin campos", "tambien mal"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()
    assert body["created"] == 0
    assert [error["line"] for error in body["errors"]] == [1, 2]


# --- Money contract: integer cents only -------------------------------------


@pytest.mark.asyncio
async def test_create_accepts_integer_cents(client):
    token = await _token_for(client)
    body = await _create_ingredient(client, token, price=12345)
    assert body["price_per_unit"] == 12345


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_price", ["5", 5.0, True])
async def test_create_rejects_non_integer_money(client, bad_price):
    token = await _token_for(client)
    response = await client.post(
        "/api/v1/ingredients",
        json={"name": "Harina", "unit": "kg", "price_per_unit": bad_price},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

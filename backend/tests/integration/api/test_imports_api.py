import pytest
import pytest_asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from main import app
from data.db import get_db
from data.models import CustomerORM, IngredientORM, ImportSessionORM
from data.repositories.sql_settings_repository import SQLSettingsRepository
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.dependencies import get_user_repository
from api.v1.settings.dependencies import get_settings_repository
from api.v1.imports.adapters.ingredients_adapter import IngredientsAdapter
from domain.models import User, UserRole

INGREDIENTS_CSV = (
    "nombre,cantidad,unidad,precio\n"
    "Harina 000,10,kg,1200\n"
    "Aceite,1,L,300\n"
)
INGREDIENTS_SEMI_CSV = (
    "nombre;cantidad;unidad;precio\n"
    "Harina 000;10;kg;1200\n"
    "Azúcar;2;kg;1.200,5\n"
)
PRODUCTS_CSV = (
    "nombre,categoria,unidad,costo_unitario,precio_venta,stock_inicial\n"
    "Torta de limón,Tortas,unidad,3000,6000,10\n"
    "Factura,Facturas,unidad,1200,2500,20\n"
)
CUSTOMERS_CSV = (
    "nombre,telefono\n"
    "María González,11 5555-0101\n"
    "Pedro López,11-5555-0202\n"
)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_settings_repository():
        yield SQLSettingsRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_settings_repository] = override_get_settings_repository
    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="other@example.com", role=UserRole.CUSTOMER)
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides = {}


async def _login(client: AsyncClient, email: str = "admin@example.com") -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _upload_body(client: AsyncClient, token: str, csv_text: str, entity: str):
    return await client.post(
        "/api/v1/imports",
        files={"file": ("upload.csv", csv_text.encode("utf-8"), "text/csv")},
        data={"entity": entity},
        headers={"Authorization": f"Bearer {token}"},
    )




@pytest.mark.asyncio
async def test_imports_requires_authentication(client):
    assert (await client.get("/api/v1/imports/template?entity=ingredients")).status_code == 401
    assert (await client.post("/api/v1/imports", data={"entity": "ingredients"})).status_code == 401
    assert (await client.get("/api/v1/imports/x/rows")).status_code == 401
    assert (await client.post("/api/v1/imports/x/confirm")).status_code == 401
    assert (await client.delete("/api/v1/imports/x")).status_code == 401


@pytest.mark.asyncio
async def test_imports_forbidden_for_non_admin(client):
    token = await _login(client, "other@example.com")
    response = await client.get(
        "/api/v1/imports/template?entity=ingredients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403




@pytest.mark.asyncio
async def test_template_returns_csv_of_entity_columns(client):
    token = await _login(client)
    response = await client.get(
        "/api/v1/imports/template?entity=ingredients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.text.splitlines()[0] == "nombre;cantidad;unidad;precio"


@pytest.mark.asyncio
async def test_template_unknown_entity_422(client):
    token = await _login(client)
    response = await client.get(
        "/api/v1/imports/template?entity=widgets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
    assert "widgets" in response.json()["detail"]["message"]




@pytest.mark.asyncio
async def test_upload_valid_stages(client):
    token = await _login(client)
    response = await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["total_rows"] == 2
    assert body["valid_rows"] == 2
    assert body["invalid_rows"] == 0
    assert body["import_id"]


@pytest.mark.asyncio
async def test_upload_ignores_column_order(client):
    token = await _login(client)
    csv = "precio,unidad,nombre,cantidad\n1200,kg,Harina 000,10\n"
    response = await _upload_body(client, token, csv, "ingredients")
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_upload_unknown_column_422_no_staging(client, db_session):
    token = await _login(client)
    csv = "nombre,cantidad,unidad,precio,costo\n1200,kg,Harina,10,X\n"
    response = await _upload_body(client, token, csv, "ingredients")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["extra"] == ["costo"]
    count = (
        await db_session.execute(select(func.count()).select_from(ImportSessionORM))
    ).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_upload_missing_column_422(client):
    token = await _login(client)
    csv = "nombre,cantidad,unidad\nHarina,10,kg\n"
    response = await _upload_body(client, token, csv, "ingredients")
    assert response.status_code == 422
    assert "precio" in response.json()["detail"]["missing"]


@pytest.mark.asyncio
async def test_upload_empty_file_422(client):
    token = await _login(client)
    response = await client.post(
        "/api/v1/imports",
        files={"file": ("vacio.csv", b"", "text/csv")},
        data={"entity": "ingredients"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_oversize_413(client):
    token = await _login(client)
    big = "nombre,cantidad,unidad,precio\n" + ("Harina,1,kg,10" + "x" * 600 + "\n") * 10000
    response = await client.post(
        "/api/v1/imports",
        files={"file": ("big.csv", big.encode("utf-8"), "text/csv")},
        data={"entity": "ingredients"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_mixed_rows_reports_invalid(client):
    token = await _login(client)
    csv = (
        "nombre,cantidad,unidad,precio\n"
        "Harina,10,kg,1200\n"
        ",10,kg,1200\n"
        "Azúcar,1,kg,abc\n"
    )
    response = await _upload_body(client, token, csv, "ingredients")
    assert response.status_code == 201
    body = response.json()
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 2
    assert len(body["first_errors"]) == 2


@pytest.mark.asyncio
async def test_upload_bom_and_semicolon(client):
    token = await _login(client)
    csv_bytes = INGREDIENTS_SEMI_CSV.encode("utf-8-sig")
    response = await client.post(
        "/api/v1/imports",
        files={"file": ("semi.csv", csv_bytes, "text/csv")},
        data={"entity": "ingredients"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["valid_rows"] == 2




@pytest.mark.asyncio
async def test_rows_returns_session_and_rows(client):
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    response = await client.get(
        f"/api/v1/imports/{import_id}/rows",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["session"]["entity"] == "ingredients"
    assert body["rows"][0]["status"] == "valid"
    assert body["rows"][0]["row_number"] == 1


@pytest.mark.asyncio
async def test_rows_filter_invalid(client):
    token = await _login(client)
    csv = "nombre,cantidad,unidad,precio\n,1,kg,10\nOk,1,kg,10\n"
    import_id = (await _upload_body(client, token, csv, "ingredients")).json()["import_id"]
    response = await client.get(
        f"/api/v1/imports/{import_id}/rows?status=invalid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["rows"][0]["status"] == "invalid"
    assert body["rows"][0]["errors"]


@pytest.mark.asyncio
async def test_rows_unknown_id_404(client):
    token = await _login(client)
    response = await client.get(
        "/api/v1/imports/00000000-0000-4000-8000-000000000000/rows",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rows_scoped_by_owner(client, db_session):
    await SQLUserRepository(db_session).save(
        User(email="admin2@example.com", role=UserRole.ADMIN)
    )
    admin_token = await _login(client, "admin@example.com")
    other_token = await _login(client, "admin2@example.com")
    import_id = (await _upload_body(client, admin_token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    response = await client.get(
        f"/api/v1/imports/{import_id}/rows",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404




@pytest.mark.asyncio
async def test_confirm_inserts_valid_ingredients(client, db_session):
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    response = await client.post(
        f"/api/v1/imports/{import_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert body["status"] == "confirmed"
    count = (await db_session.execute(select(func.count()).select_from(IngredientORM))).scalar()
    assert count == 2


@pytest.mark.asyncio
async def test_confirm_skips_duplicates(client, db_session):
    token = await _login(client)
    db_session.add(
        IngredientORM(
            id=str(uuid.uuid4()),
            name="Harina 000",
            unit="kg",
            price_per_unit="999",
            stock_qty="0",
            low_stock_threshold="0",
        )
    )
    await db_session.commit()
    csv = "nombre,cantidad,unidad,precio\nHarina 000,10,kg,1200\nAceite,1,L,300\n"
    import_id = (await _upload_body(client, token, csv, "ingredients")).json()["import_id"]
    response = await client.post(
        f"/api/v1/imports/{import_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()
    assert body["created"] == 1
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_confirm_twice_409(client):
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    first = await client.post(f"/api/v1/imports/{import_id}/confirm", headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 200
    second = await client.post(f"/api/v1/imports/{import_id}/confirm", headers={"Authorization": f"Bearer {token}"})
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_confirm_unknown_404(client):
    token = await _login(client)
    response = await client.post(
        "/api/v1/imports/00000000-0000-4000-8000-000000000000/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_rolls_back_on_insert_error(client, db_session, monkeypatch):

    async def boom(session, data):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(IngredientsAdapter, "insert", staticmethod(boom))
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    with pytest.raises(RuntimeError, match="fallo simulado"):
        await client.post(
            f"/api/v1/imports/{import_id}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
    count = (await db_session.execute(select(func.count()).select_from(IngredientORM))).scalar()
    assert count == 0




@pytest.mark.asyncio
async def test_delete_discards(client, db_session):
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    response = await client.delete(
        f"/api/v1/imports/{import_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "discarded"
    rows_response = await client.get(
        f"/api/v1/imports/{import_id}/rows",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rows_response.status_code == 200
    assert rows_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_confirmed_409(client):
    token = await _login(client)
    import_id = (await _upload_body(client, token, INGREDIENTS_CSV, "ingredients")).json()["import_id"]
    await client.post(f"/api/v1/imports/{import_id}/confirm", headers={"Authorization": f"Bearer {token}"})
    response = await client.delete(
        f"/api/v1/imports/{import_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_unknown_404(client):
    token = await _login(client)
    response = await client.delete(
        "/api/v1/imports/00000000-0000-4000-8000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404




@pytest.mark.asyncio
async def test_products_confirm_v1_no_inserts(client, db_session):
    token = await _login(client)
    import_id = (await _upload_body(client, token, PRODUCTS_CSV, "products")).json()["import_id"]
    response = await client.post(
        f"/api/v1/imports/{import_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 0
    assert "receta" in body["message"]
    from data.models import ProductORM
    count = (await db_session.execute(select(func.count()).select_from(ProductORM))).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_customers_confirm_creates_and_dedups(client, db_session):
    token = await _login(client)
    csv = (
        "nombre,telefono\n"
        "María González,11 5555-0101\n"
        "María González,1155550101\n"
        "Pedro López,11-5555-0202\n"
    )
    import_id = (await _upload_body(client, token, csv, "customers")).json()["import_id"]
    response = await client.post(
        f"/api/v1/imports/{import_id}/confirm",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = response.json()
    assert body["created"] == 2
    assert body["skipped"] == 1
    count = (await db_session.execute(select(func.count()).select_from(CustomerORM))).scalar()
    assert count == 2

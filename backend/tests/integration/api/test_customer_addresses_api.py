"""Integration tests for the Customer Address Book API (RF-P11-09, C2).

Covers auth (401/403), CRUD on /customers/me/addresses, the max-5 rule
(422), the exactly-one-default invariant (first created is default,
PATCH is_default=true demotes the previous one in the same transaction),
default promotion on delete, 409 when deleting the only address, and
anti-probing (other customers' addresses -> 404, never 403).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event

from api.v1.auth.dependencies import get_user_repository
from api.v1.customers.dependencies import get_customer_address_repository
from data.db import get_db
from data.models import Base
from data.repositories.sql_customer_address_repository import (
    SQLCustomerAddressRepository,
)
from data.repositories.sql_user_repository import SQLUserRepository
from domain.models import User, UserRole

from main import app


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Registrar accent_fold para compatibilidad con metadatos que lo usan.
    from data.accent import accent_fold

    @event.listens_for(engine.sync_engine, "connect")
    def _register_sqlite_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "accent_fold", 1, accent_fold, deterministic=True
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_address_repo():
        yield SQLCustomerAddressRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_customer_address_repository] = (
        override_get_address_repo
    )

    await SQLUserRepository(db_session).save(
        User(email="admin@example.com", role=UserRole.ADMIN)
    )
    await SQLUserRepository(db_session).save(
        User(email="customer@example.com", role=UserRole.CUSTOMER)
    )
    await SQLUserRepository(db_session).save(
        User(email="business@example.com", role=UserRole.NEGOCIO)
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


# ─── Helpers ────────────────────────────────────────────────────────────

PATH = "/api/v1/customers/me/addresses"


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _customer_token(client: AsyncClient) -> str:
    return await _token_for(client, "customer@example.com")


async def _other_token(client: AsyncClient) -> str:
    return await _token_for(client, "other@example.com")


async def _create(
    client: AsyncClient, token: str, **fields
) -> dict:
    payload = {"street_line_1": "Calle Falsa 123", **fields}
    response = await client.post(
        PATH, json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201, response.text
    return response.json()["address"]


# ─── Auth tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_requires_auth(client):
    """Sin token → 401."""
    response = await client.get(PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_requires_auth(client):
    """Sin token → 401."""
    response = await client.post(
        PATH, json={"street_line_1": "Calle Falsa 123"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_forbidden(client):
    """Admin no tiene "mis direcciones" → 403 (convención del repo)."""
    response = await client.post("/api/v1/auth/login", json={"email": "admin@example.com"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get(PATH, headers=headers)).status_code == 403
    assert (
        await client.post(PATH, json={"street_line_1": "x"}, headers=headers)
    ).status_code == 403


# ─── List ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_empty(client):
    """GET devuelve items vacios al inicio."""
    token = await _customer_token(client)
    response = await client.get(
        PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_list_includes_is_default(client):
    """Cada item expone is_default."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _create(client, token)

    body = (await client.get(PATH, headers=headers)).json()
    assert len(body["items"]) == 1
    assert body["items"][0]["is_default"] is True


# ─── Create ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_first_becomes_default(client):
    """La primera dirección creada pasa a default."""
    token = await _customer_token(client)
    address = await _create(client, token)
    assert address["is_default"] is True
    assert "id" in address
    assert address["street_line_1"] == "Calle Falsa 123"


@pytest.mark.asyncio
async def test_create_second_not_default(client):
    """Segunda dirección: is_default=false, sigue existiendo exactamente 1 default."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _create(client, token, street_line_1="Casa 1")
    second = await _create(client, token, street_line_1="Avenida Siesta 42")
    assert second["is_default"] is False

    items = (await client.get(PATH, headers=headers)).json()["items"]
    defaults = [item for item in items if item["is_default"]]
    assert len(defaults) == 1


@pytest.mark.asyncio
async def test_create_full_payload_roundtrip(client):
    """Todos los campos opcionales se persisten."""
    token = await _customer_token(client)
    address = await _create(
        client,
        token,
        street_line_2="Piso 3, Depto 7",
        city="Toscana",
        postal_code="1431",
        province="Buenos Aires",
        phone="+5491112345678",
    )
    assert address["street_line_2"] == "Piso 3, Depto 7"
    assert address["city"] == "Toscana"
    assert address["postal_code"] == "1431"
    assert address["province"] == "Buenos Aires"
    assert address["phone"] == "+5491112345678"


@pytest.mark.asyncio
async def test_create_sixth_rejected(client):
    """Máx. 5 por cliente: la 6.ª POST → 422."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(5):
        assert (
            await client.post(
                PATH,
                json={"street_line_1": f"Calle {i}"},
                headers=headers,
            )
        ).status_code == 201

    sixth = await client.post(
        PATH,
        json={"street_line_1": "Calle 5"},
        headers=headers,
    )
    assert sixth.status_code == 422


@pytest.mark.asyncio
async def test_create_missing_street_line_1_rejected(client):
    """street_line_1 es requerida → 422."""
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"city": "Toscana"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_blank_street_line_1_rejected(client):
    """street_line_1 solo espacios → 422."""
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"street_line_1": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_street_line_1_too_long_rejected(client):
    """street_line_1 > 120 → 422."""
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"street_line_1": "a" * 121},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ─── Patch ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_updates_fields(client):
    """PATCH actualiza campos y devuelve 200."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    address = await _create(client, token)
    updated = await client.patch(
        f"{PATH}/{address['id']}",
        json={"city": "Toscana", "phone": "+54911999999999"},
        headers=headers,
    )
    assert updated.status_code == 200
    body = updated.json()["address"]
    assert body["city"] == "Toscana"
    assert body["phone"] == "+54911999999999"


@pytest.mark.asyncio
async def test_patch_null_and_empty_string_clear_optional_fields(client):
    """PATCH con null o "" limpia campos opcionales (ausente != null)."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    address = await _create(client, token)
    await client.patch(
        f"{PATH}/{address['id']}",
        json={"city": "Toscana", "phone": "+54911999999999"},
        headers=headers,
    )

    cleared = await client.patch(
        f"{PATH}/{address['id']}",
        json={"phone": "", "city": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    body = cleared.json()["address"]
    assert body["phone"] is None
    assert body["city"] is None
    assert body["street_line_1"] == address["street_line_1"]


@pytest.mark.asyncio
async def test_patch_is_default_true_demotes_previous(client):
    """PATCH is_default=true: la nueva pasa a default y la anterior no."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token, street_line_1="Casa 1")
    second = await _create(client, token, street_line_1="Casa 2")

    updated = await client.patch(
        f"{PATH}/{second['id']}",
        json={"is_default": True},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["address"]["is_default"] is True

    items = (await client.get(PATH, headers=headers)).json()["items"]
    by_id = {item["id"]: item for item in items}
    assert by_id[first["id"]]["is_default"] is False
    assert by_id[second["id"]]["is_default"] is True
    assert sum(item["is_default"] for item in items) == 1


@pytest.mark.asyncio
async def test_patch_unset_default_rejected(client):
    """is_default=false sobre la actual default rompe el invariant (exactly 1) → 422."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token)
    second = await _create(client, token, street_line_1="Casa 2")
    first_id = first["id"]

    response = await client.patch(
        f"{PATH}/{first_id}",
        json={"is_default": False},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_empty_body_rejected(client):
    """PATCH sin campos → 422."""
    token = await _customer_token(client)
    address = await _create(client, token)

    response = await client.patch(
        f"{PATH}/{address['id']}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_missing_rejected(client):
    """street_line_1 vacia en PATCH → 422."""
    token = await _customer_token(client)
    address = await _create(client, token)

    response = await client.patch(
        f"{PATH}/{address['id']}",
        json={"street_line_1": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_not_found(client):
    """id inexistente → 404."""
    token = await _customer_token(client)
    response = await client.patch(
        f"{PATH}/no-such-id",
        json={"city": "Toscana"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ─── Delete ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_only_address_rejected(client):
    """Borrar la única dirección → 409 (no se deja al cliente sin default)."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    address = await _create(client, token)
    response = await client.delete(f"{PATH}/{address['id']}", headers=headers)
    assert response.status_code == 409

    # La dirección sigue existiendo
    items = (await client.get(PATH, headers=headers)).json()["items"]
    assert len(items) == 1


@pytest.mark.asyncio
async def test_delete_non_default_ok(client):
    """Borrar una no-default → 204; el default no cambia."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token, street_line_1="Casa 1")
    second = await _create(client, token, street_line_1="Casa 2")

    response = await client.delete(f"{PATH}/{second['id']}", headers=headers)
    assert response.status_code == 204

    items = (await client.get(PATH, headers=headers)).json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == first["id"]
    assert items[0]["is_default"] is True


@pytest.mark.asyncio
async def test_delete_default_promotes_oldest(client):
    """Borrar la default → la primera restante (por created_at) pasa a default."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token, street_line_1="Casa 1")
    third = await _create(client, token, street_line_1="Casa 3")

    # Hacer default a la más reciente para que la promoción no sea trivial.
    promote = await client.patch(
        f"{PATH}/{third['id']}",
        json={"is_default": True},
        headers=headers,
    )
    assert promote.status_code == 200

    response = await client.delete(f"{PATH}/{third['id']}", headers=headers)
    assert response.status_code == 204

    items = (await client.get(PATH, headers=headers)).json()["items"]
    defaults = [item for item in items if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == first["id"]


@pytest.mark.asyncio
async def test_delete_only_two_promotes_survivor(client):
    """Con 2 direcciones, borrar la default deja default a la sobreviviente."""
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token, street_line_1="Casa 1")
    second = await _create(client, token, street_line_1="Casa 2")

    response = await client.delete(f"{PATH}/{first['id']}", headers=headers)
    assert response.status_code == 204

    items = (await client.get(PATH, headers=headers)).json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == second["id"]
    assert items[0]["is_default"] is True


@pytest.mark.asyncio
async def test_delete_not_found(client):
    """id inexistente → 404."""
    token = await _customer_token(client)
    response = await client.delete(
        f"{PATH}/no-such-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ─── Anti-probing (other customers' addresses) ──────────────────────────

@pytest.mark.asyncio
async def test_other_customer_list_is_empty(client):
    """El otro cliente no ve las direcciones de este."""
    token = await _customer_token(client)
    other = await _other_token(client)

    await _create(client, token)

    body = (
        await client.get(PATH, headers={"Authorization": f"Bearer {other}"})
    ).json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_other_customer_patch_returns_404(client):
    """Ajenas → 404 (nunca 403 que confirme existencia)."""
    token = await _customer_token(client)
    other = await _other_token(client)

    address = await _create(client, token)

    response = await client.patch(
        f"{PATH}/{address['id']}",
        json={"city": "Hackeada"},
        headers={"Authorization": f"Bearer {other}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_other_customer_delete_returns_404(client):
    """Ajenas → 404 (nunca 403)."""
    token = await _customer_token(client)
    other = await _other_token(client)

    address = await _create(client, token)

    response = await client.delete(
        f"{PATH}/{address['id']}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert response.status_code == 404

    # La dirección sigue intacta para su dueño
    items = (
        await client.get(
            PATH, headers={"Authorization": f"Bearer {token}"}
        )
    ).json()["items"]
    assert len(items) == 1


# ─── Role coverage ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_business_role_can_use_address_book(client):
    """El rol negocio (cliente de negocio) también usa su libro."""
    response = await client.post(
        "/api/v1/auth/login", json={"email": "business@example.com"}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        PATH,
        json={"street_line_1": "Av. del Negocio 1"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["address"]["is_default"] is True

    listed = await client.get(PATH, headers=headers)
    assert len(listed.json()["items"]) == 1


import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.customers.dependencies import get_customer_address_repository
from data.db import get_db
from data.repositories.sql_customer_address_repository import (
    SQLCustomerAddressRepository,
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



PATH = "/api/v1/customers/me/addresses"


async def _token_for(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200
    return response.cookies["auth_token"]


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



@pytest.mark.asyncio
async def test_list_requires_auth(client):
    response = await client.get(PATH)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_requires_auth(client):
    response = await client.post(
        PATH, json={"street_line_1": "Calle Falsa 123"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_forbidden(client):
    response = await client.post("/api/v1/auth/login", json={"email": "admin@example.com"})
    token = response.cookies["auth_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get(PATH, headers=headers)).status_code == 403
    assert (
        await client.post(PATH, json={"street_line_1": "x"}, headers=headers)
    ).status_code == 403



@pytest.mark.asyncio
async def test_list_empty(client):
    token = await _customer_token(client)
    response = await client.get(
        PATH, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_list_includes_is_default(client):
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    await _create(client, token)

    body = (await client.get(PATH, headers=headers)).json()
    assert len(body["items"]) == 1
    assert body["items"][0]["is_default"] is True



@pytest.mark.asyncio
async def test_create_first_becomes_default(client):
    token = await _customer_token(client)
    address = await _create(client, token)
    assert address["is_default"] is True
    assert "id" in address
    assert address["street_line_1"] == "Calle Falsa 123"


@pytest.mark.asyncio
async def test_create_second_not_default(client):
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
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"city": "Toscana"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_blank_street_line_1_rejected(client):
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"street_line_1": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_street_line_1_too_long_rejected(client):
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"street_line_1": "a" * 121},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422



@pytest.mark.asyncio
async def test_patch_updates_fields(client):
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
    token = await _customer_token(client)
    response = await client.patch(
        f"{PATH}/no-such-id",
        json={"city": "Toscana"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404



@pytest.mark.asyncio
async def test_delete_only_address_rejected(client):
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    address = await _create(client, token)
    response = await client.delete(f"{PATH}/{address['id']}", headers=headers)
    assert response.status_code == 409

    items = (await client.get(PATH, headers=headers)).json()["items"]
    assert len(items) == 1


@pytest.mark.asyncio
async def test_delete_non_default_ok(client):
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
    token = await _customer_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await _create(client, token, street_line_1="Casa 1")
    third = await _create(client, token, street_line_1="Casa 3")

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
    token = await _customer_token(client)
    response = await client.delete(
        f"{PATH}/no-such-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404



@pytest.mark.asyncio
async def test_other_customer_list_is_empty(client):
    token = await _customer_token(client)
    other = await _other_token(client)

    await _create(client, token)

    body = (
        await client.get(PATH, headers={"Authorization": f"Bearer {other}"})
    ).json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_other_customer_patch_returns_404(client):
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
    token = await _customer_token(client)
    other = await _other_token(client)

    address = await _create(client, token)

    response = await client.delete(
        f"{PATH}/{address['id']}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert response.status_code == 404

    items = (
        await client.get(
            PATH, headers={"Authorization": f"Bearer {token}"}
        )
    ).json()["items"]
    assert len(items) == 1



@pytest.mark.asyncio
async def test_business_role_can_use_address_book(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "business@example.com"}
    )
    token = response.cookies["auth_token"]
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



async def test_db_rejects_second_default_for_same_user(client, db_session):
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from data.models import CustomerAddressORM, UserORM

    user_id = (
        await db_session.execute(
            select(UserORM.id).where(UserORM.email == "customer@example.com")
        )
    ).scalar_one()
    other_id = (
        await db_session.execute(
            select(UserORM.id).where(UserORM.email == "other@example.com")
        )
    ).scalar_one()

    def _row(address_id: str, owner: str, is_default: bool):
        return CustomerAddressORM(
            id=address_id,
            user_id=owner,
            street_line_1="Calle 1",
            is_default=is_default,
        )

    db_session.add_all(
        [
            _row("a1", user_id, True),
            _row("a2", user_id, False),
            _row("a3", user_id, False),
            _row("b1", other_id, True),
        ]
    )
    await db_session.commit()

    db_session.add(_row("a4", user_id, True))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_integrity_error_on_default_index_maps_to_409(client, db_session):
    from sqlalchemy.exc import IntegrityError

    class _ConflictingRepo(SQLCustomerAddressRepository):
        async def insert(self, address, user_id):
            raise IntegrityError("INSERT", {}, Exception("unique violation"))

    async def override_repo():
        yield _ConflictingRepo(db_session)

    app.dependency_overrides[get_customer_address_repository] = override_repo
    token = await _customer_token(client)
    response = await client.post(
        PATH,
        json={"street_line_1": "Calle Falsa 123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409

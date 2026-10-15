import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.db import get_db
from api.v1.auth.dependencies import get_user_repository
from domain.models import User, UserRole


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
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

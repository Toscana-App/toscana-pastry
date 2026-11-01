"""Tests for require_role guard (S1)."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

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
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
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


# ---- require_role: NEGOCIO endpoint ----


@pytest.mark.asyncio
async def test_require_role_negocio_allows_negocio(db_session, client):
    """S1: require_role(NEGOCIO) allows NEGOCIO users."""
    await SQLUserRepository(db_session).save(
        User(id="n1", email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    token = await _token_for(client, "negocio@example.com")

    # Admin endpoint requires admin — should be 403 for negocio
    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"] or "admin" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_require_role_negocio_blocks_customer(db_session, client):
    """S1: require_role(NEGOCIO) blocks CUSTOMER users."""
    token = await _token_for(client, "customer@example.com")

    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_require_role_admin_allows_admin(db_session, client):
    """S1: require_admin still allows ADMIN."""
    await SQLUserRepository(db_session).save(
        User(id="a1", email="admin@example.com", role=UserRole.ADMIN)
    )
    token = await _token_for(client, "admin@example.com")

    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_require_role_admin_blocks_negocio(db_session, client):
    """S1: require_admin blocks NEGOCIO."""
    await SQLUserRepository(db_session).save(
        User(id="n1", email="negocio@example.com", role=UserRole.NEGOCIO)
    )
    token = await _token_for(client, "negocio@example.com")

    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"] or "admin" in response.json()["detail"].lower()

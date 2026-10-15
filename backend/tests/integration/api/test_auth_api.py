import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from datetime import datetime, timedelta
from fastapi import Depends

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_login_invalid_payload():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={})
        assert response.status_code == 400

@pytest.mark.asyncio
async def test_me_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/auth/me")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_me_authenticated(db_session):
    # Use a generator for the override
    async def get_user_repo_for_test():
        async with db_session as session:
            yield SQLUserRepository(session)

    # We need to find the actual function to override
    from api.v1.auth.router import get_user_repository
    
    # Apply override
    app.dependency_overrides[get_user_repository] = get_user_repo_for_test

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_resp = await ac.post("/api/v1/auth/login", json={"email": "test@example.com"})
            assert login_resp.status_code == 200
            token = login_resp.json()["token"]
            
            response = await ac.get(
                "/api/v1/auth/me", 
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["email"] == "test@example.com"
    finally:
        app.dependency_overrides = {}

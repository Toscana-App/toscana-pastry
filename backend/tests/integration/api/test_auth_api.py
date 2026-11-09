import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from data.repositories.sql_user_repository import SQLUserRepository
from data.db import get_db
import asyncio

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_login_invalid_payload(db_session):
    async def override_get_db():
        async with db_session as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/v1/auth/login", json={})
            assert response.status_code == 400
    finally:
        app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_me_unauthorized(db_session):
    async def override_get_db():
        async with db_session as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/auth/me")
            assert response.status_code == 401
    finally:
        app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_me_authenticated(db_session):
    async def override_get_db():
        async with db_session as session:
            yield session
    
    async def get_user_repo_for_test():
        async with db_session as session:
            yield SQLUserRepository(session)

    app.dependency_overrides[get_db] = override_get_db
    from api.v1.auth.router import get_user_repository
    app.dependency_overrides[get_user_repository] = get_user_repo_for_test

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_resp = await ac.post("/api/v1/auth/login", json={"email": "test@example.com"})
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            refresh_token = login_resp.json()["refresh_token"]
            
            response = await ac.get(
                "/api/v1/auth/me", 
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            assert response.json()["email"] == "test@example.com"

            refresh_resp = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
            assert refresh_resp.status_code == 200
            assert "access_token" in refresh_resp.json()
            
            bad_refresh_resp = await ac.post("/api/v1/auth/refresh", json={"refresh_token": "invalid_token"})
            assert bad_refresh_resp.status_code == 401
            
    finally:
        app.dependency_overrides = {}

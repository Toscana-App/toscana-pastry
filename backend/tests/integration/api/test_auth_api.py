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

REFRESH_PATH = "/api/v1/auth"


@pytest.fixture
def auth_app(db_session):
    async def override_get_db():
        async with db_session as session:
            yield session

    async def get_user_repo_for_test():
        async with db_session as session:
            yield SQLUserRepository(session)

    from api.v1.auth.router import get_user_repository

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_repository] = get_user_repo_for_test
    yield app
    app.dependency_overrides = {}


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")


def _set_cookies(response) -> dict[str, str]:
    return {
        header.split("=", 1)[0]: header
        for header in response.headers.get_list("set-cookie")
    }


async def _login(ac):
    response = await ac.post("/api/v1/auth/login", json={"email": "test@example.com"})
    assert response.status_code == 200
    return response


@pytest.mark.asyncio
async def test_login_sets_hardened_session_cookies(auth_app):
    async with _client() as ac:
        response = await _login(ac)

    body = response.json()
    assert "access_token" not in body and "refresh_token" not in body
    cookies = _set_cookies(response)
    for name in ("auth_token", "refresh_token"):
        header = cookies[name].lower()
        assert "httponly" in header
        assert "secure" in header
        assert "samesite=strict" in header
    assert "path=/;" in cookies["auth_token"].lower() + ";"
    assert f"path={REFRESH_PATH}".lower() in cookies["refresh_token"].lower()


@pytest.mark.asyncio
async def test_me_authenticated_with_access_cookie(auth_app):
    async with _client() as ac:
        await _login(ac)
        response = await ac.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_me_still_accepts_bearer_header(auth_app):
    async with _client() as ac:
        login = await _login(ac)
        token = ac.cookies.get("auth_token")
        ac.cookies.clear()
        response = await ac.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

    assert login.status_code == 200
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_rotates_both_cookies(auth_app):
    async with _client() as ac:
        await _login(ac)
        old_refresh = ac.cookies.get("refresh_token", path=REFRESH_PATH)
        response = await ac.post("/api/v1/auth/refresh")
        new_refresh = ac.cookies.get("refresh_token", path=REFRESH_PATH)
        me = await ac.get("/api/v1/auth/me")

    assert response.status_code == 204
    assert set(_set_cookies(response)) == {"auth_token", "refresh_token"}
    assert new_refresh != old_refresh
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_reusing_rotated_refresh_token_revokes_the_family(auth_app):
    async with _client() as ac:
        await _login(ac)
        stolen = ac.cookies.get("refresh_token", path=REFRESH_PATH)
        assert (await ac.post("/api/v1/auth/refresh")).status_code == 204
        legit = ac.cookies.get("refresh_token", path=REFRESH_PATH)

        ac.cookies.clear()
        reuse = await ac.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": stolen}
        )
        ac.cookies.clear()
        after = await ac.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": legit}
        )

    assert reuse.status_code == 401
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_or_with_invalid_cookie_is_401(auth_app):
    async with _client() as ac:
        missing = await ac.post("/api/v1/auth/refresh")
        invalid = await ac.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": "invalid_token"}
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session_and_clears_cookies(auth_app):
    async with _client() as ac:
        await _login(ac)
        refresh = ac.cookies.get("refresh_token", path=REFRESH_PATH)
        response = await ac.post("/api/v1/auth/logout")
        ac.cookies.clear()
        after = await ac.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": refresh}
        )

    assert response.status_code == 204
    cleared = _set_cookies(response)
    assert set(cleared) == {"auth_token", "refresh_token"}
    assert all("max-age=0" in h.lower() for h in cleared.values())
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_logout_without_session_is_204(auth_app):
    async with _client() as ac:
        response = await ac.post("/api/v1/auth/logout")

    assert response.status_code == 204

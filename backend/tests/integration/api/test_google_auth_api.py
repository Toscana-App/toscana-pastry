import pytest
from httpx import ASGITransport, AsyncClient

import domain.auth.google as google_domain
from core.config import settings as app_settings
from domain.models import User, UserRole
from main import app
from data.db import get_db
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.cookies import GOOGLE_PREAUTH_COOKIE

NONCE_PATH = "/api/v1/auth/google/nonce"
SIGNIN_PATH = "/api/v1/auth/google/signin"

SAME_ORIGIN = {"sec-fetch-site": "same-origin"}
CROSS_SITE = {"sec-fetch-site": "cross-site", "origin": "https://evil.example"}


@pytest.fixture
def google_config(monkeypatch):
    monkeypatch.setattr(app_settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(app_settings, "GOOGLE_AUTO_CREATE", True)


class _FakeVerify:

    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.calls = 0

    def __call__(self, credential, transport, client_id):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        assert self.payload is not None
        return dict(self.payload)


def _payload(nonce, email="user@gmail.com", sub="google-sub-1",
             email_verified=True):
    return {
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "aud": "test-client-id",
        "nonce": nonce,
    }


@pytest.fixture
def google_app(db_session, google_config):
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


async def _fetch_nonce(ac) -> str:
    response = await ac.get(NONCE_PATH, headers=SAME_ORIGIN)
    assert response.status_code == 200
    return response.json()["nonce"]


@pytest.mark.asyncio
async def test_nonce_sets_preauth_cookie_and_returns_nonce(google_app):
    async with _client() as ac:
        response = await ac.get(NONCE_PATH, headers=SAME_ORIGIN)

    assert response.status_code == 200
    nonce = response.json()["nonce"]
    assert nonce
    header = _set_cookies(response).get(GOOGLE_PREAUTH_COOKIE, "")
    assert "httponly" in header.lower()
    assert "secure" in header.lower()
    assert "samesite=lax" in header.lower()
    assert "max-age=600" in header.lower()
    assert "path=/api/v1/auth" in header.lower()


@pytest.mark.asyncio
async def test_signin_cross_site_is_403_before_any_verification(
    google_app, monkeypatch
):
    verify = _FakeVerify(payload=_payload("n"))
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        ac.cookies.set(GOOGLE_PREAUTH_COOKIE, "anything")
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=CROSS_SITE
        )

    assert response.status_code == 403
    assert verify.calls == 0


@pytest.mark.asyncio
async def test_signin_missing_sec_fetch_site_with_unknown_origin_is_403(
    google_app, monkeypatch
):
    verify = _FakeVerify(payload=_payload("n"))
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        response = await ac.post(
            SIGNIN_PATH,
            json={"credential": "jwt"},
            headers={"origin": "https://evil.example"},
        )

    assert response.status_code == 403
    assert verify.calls == 0


@pytest.mark.asyncio
async def test_signin_invalid_token_is_401(google_app, monkeypatch):
    verify = _FakeVerify(exc=ValueError("Invalid JWT signature"))
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        await _fetch_nonce(ac)
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "bad"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 401
    assert "Invalid Google token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_signin_without_preauth_cookie_is_401(google_app, monkeypatch):
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        ac.cookies.clear()
    verify = _FakeVerify(payload=_payload(nonce))
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 401
    assert "nonce" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signin_nonce_mismatch_is_401(google_app, monkeypatch):
    async with _client() as ac:
        first = await _fetch_nonce(ac)
        second = await _fetch_nonce(ac)
        assert first != second
    verify = _FakeVerify(payload=_payload(first))
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        await _fetch_nonce(ac)
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_signin_happy_path_creates_user_and_sets_session_cookies(
    google_app, monkeypatch, db_session
):
    verify = _FakeVerify(payload=None)
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        verify.payload = _payload(nonce)
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "user@gmail.com"
    assert body["role"] == "customer"
    assert body["state"] == "signed_in"
    assert body["user_id"]
    assert "access_token" not in body and "refresh_token" not in body
    cookies = _set_cookies(response)
    assert "auth_token" in cookies and "refresh_token" in cookies
    for name in cookies:
        assert "httponly" in cookies[name].lower()
        assert "secure" in cookies[name].lower()
        assert "samesite=strict" in cookies[name].lower()

    from data.repositories.sql_user_repository import SQLUserRepository as _R

    async with db_session as session:
        user = await _R(session).get_by_google_id("google-sub-1")
    assert user is not None
    assert user.email == "user@gmail.com"
    assert user.role == UserRole.CUSTOMER


@pytest.mark.asyncio
async def test_signin_replay_with_same_cookie_is_401(google_app, monkeypatch):
    verify = _FakeVerify(payload=None)
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        verify.payload = _payload(nonce)
        first = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )
        second = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert first.status_code == 200
    assert second.status_code == 401
    assert "nonce" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_signin_existing_google_id_logs_in(google_app, monkeypatch, db_session):
    from data.repositories.sql_user_repository import SQLUserRepository as _R

    async with db_session as session:
        await _R(session).save(
            User(email="old@example.com", google_id="google-sub-1",
                 role=UserRole.NEGOCIO)
        )
    verify = _FakeVerify(payload=None)
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        verify.payload = _payload(
            nonce, email="current@gmail.com", sub="google-sub-1"
        )
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "signed_in"
    assert body["email"] == "old@example.com"
    assert body["role"] == "negocio"


@pytest.mark.asyncio
async def test_signin_not_configured_is_404(monkeypatch, db_session):
    monkeypatch.setattr(app_settings, "GOOGLE_CLIENT_ID", "")

    async def override_get_db():
        async with db_session as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with _client() as ac:
            nonce = await ac.get(NONCE_PATH, headers=SAME_ORIGIN)
            signin = await ac.post(
                SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
            )
    finally:
        app.dependency_overrides = {}

    assert nonce.status_code == 404
    assert signin.status_code == 404


@pytest.mark.asyncio
async def test_signin_no_account_when_auto_create_disabled(
    google_app, monkeypatch
):
    monkeypatch.setattr(app_settings, "GOOGLE_AUTO_CREATE", False)
    verify = _FakeVerify(payload=None)
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        verify.payload = _payload(nonce, email="fresh@gmail.com")
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["state"] == "no_account"
    assert "email de compra" in detail["message"]


@pytest.mark.asyncio
async def test_signin_link_pending_when_email_exists_without_google_id(
    google_app, monkeypatch, db_session
):
    from data.repositories.sql_user_repository import SQLUserRepository as _R

    async with db_session as session:
        await _R(session).save(
            User(email="user@gmail.com", role=UserRole.CUSTOMER)
        )
    verify = _FakeVerify(payload=None)
    monkeypatch.setattr(google_domain, "verify_oauth2_token", verify)
    async with _client() as ac:
        nonce = await _fetch_nonce(ac)
        verify.payload = _payload(nonce, email="user@gmail.com") | {"hd": "user"}
        response = await ac.post(
            SIGNIN_PATH, json={"credential": "jwt"}, headers=SAME_ORIGIN
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["state"] == "link_pending"


@pytest.mark.asyncio
async def test_auth_surface_is_rate_limited(google_app):
    async with _client() as ac:
        statuses = [
            (await ac.get(NONCE_PATH, headers=SAME_ORIGIN)).status_code
            for _ in range(30)
        ]
        blocked = await ac.get(NONCE_PATH, headers=SAME_ORIGIN)

    assert all(code == 200 for code in statuses)
    assert blocked.status_code == 429

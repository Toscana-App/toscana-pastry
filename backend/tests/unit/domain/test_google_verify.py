import pytest

import domain.auth.google as google_domain
from domain.auth.google import (
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    verify_google_id_token,
)

VALID_PAYLOAD = {
    "sub": "google-sub-1",
    "email": "user@gmail.com",
    "email_verified": True,
    "aud": "client-id-123",
    "nonce": "server-issued-nonce",
}


@pytest.fixture
def monkeypatched_verify(monkeypatch):
    def make(payload, raise_exc=None):
        def fake_verify(credential, transport, client_id):
            if raise_exc is not None:
                raise raise_exc
            assert credential == "jwt.value"
            assert client_id == "client-id-123"
            return dict(payload)

        monkeypatch.setattr(google_domain, "verify_oauth2_token", fake_verify)
        return fake_verify

    return make


def test_valid_payload_is_returned(monkeypatched_verify):
    monkeypatched_verify(VALID_PAYLOAD)
    payload = verify_google_id_token("jwt.value", "client-id-123")
    assert payload["sub"] == "google-sub-1"
    assert payload["email_verified"] is True


def test_email_verified_false_is_rejected(monkeypatched_verify):
    payload = dict(VALID_PAYLOAD, email_verified=False)
    monkeypatched_verify(payload)
    with pytest.raises(InvalidGoogleTokenError, match="not verified"):
        verify_google_id_token("jwt.value", "client-id-123")


def test_google_auth_exception_is_wrapped(monkeypatched_verify):
    monkeypatched_verify(None, raise_exc=ValueError("Invalid JWT token"))
    with pytest.raises(InvalidGoogleTokenError, match="Invalid JWT token"):
        verify_google_id_token("bad.token", "client-id-123")


def test_missing_sub_is_rejected(monkeypatched_verify):
    payload = dict(VALID_PAYLOAD)
    del payload["sub"]
    monkeypatched_verify(payload)
    with pytest.raises(InvalidGoogleTokenError, match="sub"):
        verify_google_id_token("jwt.value", "client-id-123")


def test_missing_email_is_rejected(monkeypatched_verify):
    payload = dict(VALID_PAYLOAD)
    del payload["email"]
    monkeypatched_verify(payload)
    with pytest.raises(InvalidGoogleTokenError, match="email"):
        verify_google_id_token("jwt.value", "client-id-123")


def test_empty_client_id_is_rejected(monkeypatched_verify):
    monkeypatched_verify(VALID_PAYLOAD)
    with pytest.raises(GoogleSignInNotConfiguredError):
        verify_google_id_token("jwt.value", "")

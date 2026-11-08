
import pytest
from domain.auth.logic import validate_google_id_token

# --- Google ID Token Validation ---

def test_validate_google_id_token_success():
    # Arrange
    valid_payload = {
        "sub": "google-user-123",
        "email": "user@example.com",
        "email_verified": True
    }
    
    # Act
    user_data = validate_google_id_token(valid_payload)
    
    # Assert
    assert user_data["google_id"] == "google-user-123"
    assert user_data["email"] == "user@example.com"

def test_validate_google_id_token_unverified_email():
    # Arrange
    invalid_payload = {
        "sub": "google-user-123",
        "email": "user@example.com",
        "email_verified": False
    }
    
    # Act & Assert
    with pytest.raises(ValueError, match="Email not verified"):
        validate_google_id_token(invalid_payload)

def test_validate_google_id_token_missing_sub():
    # Arrange
    invalid_payload = {
        "email": "user@example.com",
        "email_verified": True
    }
    
    # Act & Assert
    with pytest.raises(ValueError, match="Missing 'sub' in payload"):
        validate_google_id_token(invalid_payload)


# --- Access / refresh tokens ---

import jwt as pyjwt

from core.config import settings
from domain.auth.logic import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def test_refresh_token_carries_jti_and_family():
    token = create_refresh_token(sub="u1", jti="j1", family_id="f1")

    payload = decode_refresh_token(token)

    assert (payload["sub"], payload["jti"], payload["fam"]) == ("u1", "j1", "f1")


def test_refresh_token_is_signed_with_its_own_secret():
    token = create_refresh_token(sub="u1", jti="j1", family_id="f1")

    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def test_tokens_are_not_interchangeable():
    access = create_access_token({"sub": "u1"})
    refresh = create_refresh_token(sub="u1", jti="j1", family_id="f1")

    with pytest.raises(ValueError):
        decode_refresh_token(access)
    with pytest.raises(ValueError):
        decode_access_token(refresh)


def test_access_token_lives_access_ttl_minutes():
    payload = decode_access_token(create_access_token({"sub": "u1"}))

    assert payload["exp"] - payload["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

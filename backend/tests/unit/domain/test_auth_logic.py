
import pytest
from datetime import datetime, timedelta
from domain.auth.logic import MagicLinkToken, validate_google_id_token


def test_magic_link_token_generation_and_validation():
    user_email = "test@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    
    token = token_provider.generate()
    is_valid = token_provider.validate()
    
    assert is_valid is True
    assert token is not None

def test_magic_link_token_expiration():
    user_email = "expired@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    token = token_provider.generate()
    
    token_provider.expiry = datetime.utcnow() - timedelta(minutes=1)
    is_valid = token_provider.validate()
    
    assert is_valid is False

def test_magic_link_token_invalid_payload():
    user_email = "bad@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    token = token_provider.generate()
    
    token_provider.user_email = "attacker@example.com"
    is_valid = token_provider.validate()
    
    assert is_valid is False


def test_validate_google_id_token_success():
    valid_payload = {
        "sub": "google-user-123",
        "email": "user@example.com",
        "email_verified": True
    }
    
    user_data = validate_google_id_token(valid_payload)
    
    assert user_data["google_id"] == "google-user-123"
    assert user_data["email"] == "user@example.com"

def test_validate_google_id_token_unverified_email():
    invalid_payload = {
        "sub": "google-user-123",
        "email": "user@example.com",
        "email_verified": False
    }
    
    with pytest.raises(ValueError, match="Email not verified"):
        validate_google_id_token(invalid_payload)

def test_validate_google_id_token_missing_sub():
    invalid_payload = {
        "email": "user@example.com",
        "email_verified": True
    }
    
    with pytest.raises(ValueError, match="Missing 'sub' in payload"):
        validate_google_id_token(invalid_payload)

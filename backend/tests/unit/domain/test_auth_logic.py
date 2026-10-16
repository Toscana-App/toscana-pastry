
import pytest
from datetime import datetime, timedelta
from domain.auth.logic import MagicLinkToken, validate_google_id_token

# --- Test Case 1: Magic Link Token Logic ---

def test_magic_link_token_generation_and_validation():
    # Arrange
    user_email = "test@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    
    # Act
    token = token_provider.generate()
    is_valid = token_provider.validate()
    
    # Assert
    assert is_valid is True
    assert token is not None

def test_magic_link_token_expiration():
    # Arrange
    user_email = "expired@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    token = token_provider.generate()
    
    # Act: Simulate time jump (mocking expiration)
    # We'll simulate expiration by setting the token's expiry in the past
    token_provider.expiry = datetime.utcnow() - timedelta(minutes=1)
    is_valid = token_provider.validate()
    
    # Assert
    assert is_valid is False

def test_magic_link_token_invalid_payload():
    # Arrange
    user_email = "bad@example.com"
    token_provider = MagicLinkToken(user_email=user_email)
    token = token_provider.generate()
    
    # Act: Simulate tampering
    token_provider.user_email = "attacker@example.com"
    is_valid = token_provider.validate()
    
    # Assert
    assert is_valid is False

# --- Test Case 2: Google ID Token Validation ---

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


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

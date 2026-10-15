from datetime import datetime, timedelta
from typing import Optional
import jwt
from core.config import settings

class MagicLinkToken:
    def __init__(self, user_email: str):
        self.user_email = user_email
        self._original_email = user_email # Store original for integrity
        self.token = None
        self.expiry = None

    def generate(self) -> str:
        self.token = f"token-{self.user_email}"
        self.expiry = datetime.utcnow() + timedelta(minutes=15)
        return self.token

    def validate(self) -> bool:
        if self.expiry < datetime.utcnow():
            return False
        if self.user_email != self._original_email:
            return False
        return True

def validate_google_id_token(payload: dict) -> dict:
    if "sub" not in payload:
        raise ValueError("Missing 'sub' in payload")
    if not payload.get("email_verified"):
        raise ValueError("Email not verified")
    
    return {
        "google_id": payload["sub"],
        "email": payload["email"]
    }

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire.timestamp()})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")

import jwt
import datetime
from typing import Any, Dict

from core.config import settings


# --- Google Sign-In ---------------------------------------------------------

def validate_google_id_token(payload: Dict[str, Any]) -> Dict[str, str]:
    """Valida el payload de un ID token de Google y normaliza los datos del usuario."""
    if not payload.get("sub"):
        raise ValueError("Missing 'sub' in payload")
    if not payload.get("email_verified"):
        raise ValueError("Email not verified")
    return {"google_id": payload["sub"], "email": payload.get("email", "")}


# --- JWT (access / refresh) -------------------------------------------------

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        return payload
    except jwt.PyJWTError:
        raise ValueError("Invalid token")


def decode_refresh_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        return payload
    except jwt.PyJWTError:
        raise ValueError("Invalid refresh token")

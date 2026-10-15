import jwt
import datetime
from typing import Any, Dict, Optional

from core.config import settings


# --- Magic Link -------------------------------------------------------------

class MagicLinkToken:
    """Token de un solo uso enviado por email para autenticar sin contraseña."""

    def __init__(self, user_email: str, ttl_minutes: int = 15):
        self.user_email = user_email
        self.expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=ttl_minutes)
        self._token: Optional[str] = None
        self._issued_for: Optional[str] = None

    def generate(self) -> str:
        self._issued_for = self.user_email
        self._token = jwt.encode(
            {"sub": self.user_email, "exp": self.expiry, "type": "magic_link"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return self._token

    def validate(self) -> bool:
        if not self._token:
            return False
        if datetime.datetime.utcnow() > self.expiry:
            return False
        # El email no puede cambiar entre emisión y validación (anti-tampering).
        if self._issued_for != self.user_email:
            return False
        try:
            payload = jwt.decode(
                self._token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
        except jwt.PyJWTError:
            return False
        return payload.get("sub") == self.user_email


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

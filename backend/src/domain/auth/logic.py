import jwt
import datetime
from typing import Any, Dict

from core.config import settings


def validate_google_id_token(payload: Dict[str, Any]) -> Dict[str, str]:
    if not payload.get("sub"):
        raise ValueError("Missing 'sub' in payload")
    if not payload.get("email_verified"):
        raise ValueError("Email not verified")
    return {"google_id": payload["sub"], "email": payload.get("email", "")}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def create_access_token(data: Dict[str, Any]) -> str:
    now = _now()
    to_encode = data.copy()
    to_encode.update({
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(sub: str, jti: str, family_id: str) -> str:
    now = _now()
    to_encode = {
        "sub": sub,
        "jti": jti,
        "fam": family_id,
        "iat": now,
        "exp": now + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(
        to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except jwt.PyJWTError:
        raise ValueError("Invalid token")
    if payload.get("type") != "access":
        raise ValueError("Not an access token")
    return payload


def decode_refresh_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "jti", "fam"]},
        )
    except jwt.PyJWTError:
        raise ValueError("Invalid refresh token")
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")
    return payload

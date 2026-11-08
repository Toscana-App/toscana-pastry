"""Login sessions: access token + rotating refresh token.

Every refresh consumes the presented token and issues a new pair in the same
family. Presenting an already-consumed token means it was copied (stolen or
replayed), so the whole family is revoked and every holder must log in again.
"""
import datetime
import uuid
from dataclasses import dataclass

from core.config import settings
from domain.auth.logic import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from domain.repositories import RefreshTokenRepository


class InvalidRefreshToken(Exception):
    pass


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str


async def _issue(
    repo: RefreshTokenRepository, user_id: str, family_id: str
) -> SessionTokens:
    jti = uuid.uuid4().hex
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    await repo.add(jti, user_id, family_id, expires_at)
    return SessionTokens(
        access_token=create_access_token({"sub": user_id}),
        refresh_token=create_refresh_token(sub=user_id, jti=jti, family_id=family_id),
    )


async def start_session(repo: RefreshTokenRepository, user_id: str) -> SessionTokens:
    return await _issue(repo, user_id, family_id=uuid.uuid4().hex)


async def rotate_session(
    repo: RefreshTokenRepository, refresh_token: str
) -> SessionTokens:
    try:
        payload = decode_refresh_token(refresh_token)
    except ValueError as exc:
        raise InvalidRefreshToken() from exc

    # ponytail: two tabs refreshing in the same instant look like a replay and
    # log the user out. Add a short grace window for the previous jti if that
    # shows up in practice.
    if not await repo.consume(payload["jti"]):
        await repo.revoke_family(payload["fam"])
        raise InvalidRefreshToken()
    return await _issue(repo, payload["sub"], payload["fam"])


async def end_session(repo: RefreshTokenRepository, refresh_token: str) -> None:
    """Logout: revoke the whole family. A bad or missing token is a no-op."""
    try:
        payload = decode_refresh_token(refresh_token)
    except ValueError:
        return
    await repo.revoke_family(payload["fam"])

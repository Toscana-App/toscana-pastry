from fastapi import Response

from core.config import settings

ACCESS_COOKIE = "auth_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

_FLAGS = {"httponly": True, "secure": True, "samesite": "strict"}


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=refresh_max_age, path="/", **_FLAGS
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        path=REFRESH_COOKIE_PATH,
        **_FLAGS,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/", **_FLAGS)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **_FLAGS)

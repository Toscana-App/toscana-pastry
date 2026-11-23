import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from core.config import settings as app_settings
from domain.auth.google import (
    GoogleSignInNotConfiguredError,
    InvalidGoogleTokenError,
    google_json_flow_csrf_trusted,
    verify_google_id_token,
)
from domain.repositories import (
    GoogleNonceRepository,
    RefreshTokenRepository,
    UserRepository,
)
from domain.use_cases import GoogleSignIn
from domain.auth.sessions import start_session
from api.v1.auth.cookies import (
    GOOGLE_PREAUTH_COOKIE,
    set_google_preauth_cookie,
    set_session_cookies,
)
from api.v1.auth.dependencies import (
    get_google_nonce_repository,
    get_refresh_token_repository,
    get_user_repository,
)
from api.v1.auth.router import auth_limiter
from api.v1.auth.schemas import (
    GoogleNonceResponse,
    GoogleSignInRequest,
    GoogleSignInResponse,
)

logger = logging.getLogger(__name__)

NOT_CONFIGURED_DETAIL = "Google Sign-In no está configurado"
NO_ACCOUNT_DETAIL = "Revisá tu email de compra para crear tu cuenta."
LINK_PENDING_DETAIL = "Confirmá tu cuenta para enlazar Google."

router = APIRouter(
    prefix="/auth/google",
    tags=["auth"],
    dependencies=[Depends(auth_limiter.dependency())],
)


def _unauthorized_google(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _conflict(state: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": message, "state": state},
    )


@router.get("/nonce", response_model=GoogleNonceResponse)
async def google_nonce(
    response: Response,
    nonce_repo: GoogleNonceRepository = Depends(get_google_nonce_repository),
):
    if not app_settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_CONFIGURED_DETAIL,
        )
    nonce = secrets.token_urlsafe(32)
    nonce_id = await nonce_repo.issue(nonce, app_settings.GOOGLE_NONCE_TTL_SECONDS)
    set_google_preauth_cookie(response, nonce_id, app_settings.GOOGLE_NONCE_TTL_SECONDS)
    return GoogleNonceResponse(nonce=nonce)


@router.post("/signin", response_model=GoogleSignInResponse)
async def google_signin(
    request: Request,
    body: GoogleSignInRequest,
    response: Response,
    nonce_repo: GoogleNonceRepository = Depends(get_google_nonce_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    if not google_json_flow_csrf_trusted(
        request.headers.get("sec-fetch-site"),
        request.headers.get("origin"),
        app_settings.CORS_ORIGINS,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF: request origin not proven (fail closed)",
        )

    if not app_settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_CONFIGURED_DETAIL,
        )

    try:
        payload = verify_google_id_token(body.credential, app_settings.GOOGLE_CLIENT_ID)
    except InvalidGoogleTokenError as exc:
        logger.warning("google sign-in: invalid token: %s", exc)
        raise _unauthorized_google(f"Invalid Google token: {exc}")
    except GoogleSignInNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_CONFIGURED_DETAIL,
        )

    preauth = request.cookies.get(GOOGLE_PREAUTH_COOKIE)
    expected = await nonce_repo.consume(preauth) if preauth else None
    token_nonce = payload.get("nonce")
    if (
        expected is None
        or not isinstance(token_nonce, str)
        or not hmac.compare_digest(expected, token_nonce)
    ):
        logger.warning("google sign-in: nonce missing, expired or replayed")
        raise _unauthorized_google(
            "Nonce missing, expired, replayed or not server-issued"
        )

    outcome = await GoogleSignIn(
        user_repo, auto_create=app_settings.google_auto_create
    ).execute(payload)

    if outcome.state == "link_pending":
        existing_id = outcome.user.id if outcome.user is not None else None
        logger.info("google sign-in: link_pending user_id=%s", existing_id)
        raise _conflict("link_pending", LINK_PENDING_DETAIL)
    if outcome.state == "no_account":
        logger.warning("google sign-in: no_account sub=%s", payload["sub"])
        raise _conflict("no_account", NO_ACCOUNT_DETAIL)

    user = outcome.user
    if user is None:
        raise _unauthorized_google("Unexpected identity resolution state")
    tokens = await start_session(token_repo, str(user.id))
    set_session_cookies(response, tokens.access_token, tokens.refresh_token)
    logger.info("google sign-in success user_id=%s", user.id)
    return GoogleSignInResponse(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        state="signed_in",
    )

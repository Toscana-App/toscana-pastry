from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from domain.models import User
from domain.repositories import RefreshTokenRepository, UserRepository
from domain.use_cases import AuthenticateUser
from domain.auth.sessions import (
    InvalidRefreshToken,
    end_session,
    rotate_session,
    start_session,
)
from api.v1.dependencies import get_current_user
from api.v1.auth.cookies import (
    REFRESH_COOKIE,
    clear_session_cookies,
    set_session_cookies,
)
from api.v1.auth.dependencies import get_refresh_token_repository, get_user_repository
from api.v1.auth.schemas import AuthRequest, AuthResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    request: AuthRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    user_use_case = AuthenticateUser(user_repo)
    try:
        user = await user_use_case.execute(email=request.email, google_id=request.google_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    tokens = await start_session(token_repo, str(user.id))
    set_session_cookies(response, tokens.access_token, tokens.refresh_token)

    return AuthResponse(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        google_id=user.google_id
    )

@router.get("/me", response_model=UserInfo)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserInfo(
        user_id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        google_id=current_user.google_id,
    )

@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh_token(
    response: Response,
    refresh_cookie: str | None = Cookie(None, alias=REFRESH_COOKIE),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    try:
        if not refresh_cookie:
            raise InvalidRefreshToken()
        tokens = await rotate_session(token_repo, refresh_cookie)
    except InvalidRefreshToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    set_session_cookies(response, tokens.access_token, tokens.refresh_token)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_cookie: str | None = Cookie(None, alias=REFRESH_COOKIE),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
):
    if refresh_cookie:
        await end_session(token_repo, refresh_cookie)
    clear_session_cookies(response)

from fastapi import Cookie, Depends, HTTPException, status, Header
from domain.models import User, UserRole
from data.repositories.sql_user_repository import SQLUserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from data.db import get_db
from domain.auth.logic import decode_access_token
from api.v1.auth.cookies import ACCESS_COOKIE

async def get_current_user(
    authorization: str = Header(None),
    access_cookie: str | None = Cookie(None, alias=ACCESS_COOKIE),
    db: AsyncSession = Depends(get_db)
) -> User:
    # The HttpOnly cookie is the browser path; the Bearer header stays for
    # non-browser clients and tests.
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_cookie:
        token = access_cookie
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
        )
    
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user_repo = SQLUserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Authorization by role: only ADMIN passes. 403 explicit, not 404."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_role(*roles: UserRole):
    """Generic role guard: only users whose role is in *roles pass.

    Returns 403 with a clear message listing the required role(s).
    """
    role_names = ", ".join(r.value for r in roles)

    def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {role_names}",
            )
        return current_user

    return _guard

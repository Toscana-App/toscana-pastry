from fastapi import Cookie, Depends, HTTPException, Query, status, Header
from domain.models import User, UserRole
from data.repositories.sql_user_repository import SQLUserRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from data.db import get_db
from domain.auth.logic import decode_access_token
from api.v1.auth.cookies import ACCESS_COOKIE

async def set_rls_context(db: AsyncSession, user: User) -> None:
    bind = getattr(db, "bind", None)
    if bind is None or bind.dialect.name != "postgresql":
        return
    await db.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, false),"
            " set_config('app.current_role', :role, false)"
        ),
        {"user_id": user.id, "role": user.role.value},
    )

async def set_rls_webhook_order(db: AsyncSession, order_id: str) -> None:
    bind = getattr(db, "bind", None)
    if bind is None or bind.dialect.name != "postgresql":
        return
    await db.execute(
        text("SELECT set_config('app.webhook_order_id', :order_id, false)"),
        {"order_id": order_id},
    )


async def get_current_user(
    authorization: str = Header(None),
    access_cookie: str | None = Cookie(None, alias=ACCESS_COOKIE),
    db: AsyncSession = Depends(get_db)
) -> User:
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
    await set_rls_context(db, user)
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_admin_or_audience(
    audience: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> User:
    if audience is None and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_role(*roles: UserRole):
    role_names = ", ".join(r.value for r in roles)

    def _guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {role_names}",
            )
        return current_user

    return _guard

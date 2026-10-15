from fastapi import APIRouter, Depends, HTTPException, status, Header
from domain.use_cases.authenticate_user import AuthenticateUser
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.schemas import AuthRequest, AuthResponse, UserInfo
from core.config import settings
from domain.auth.logic import create_access_token
from sqlalchemy.ext.asyncio import AsyncSession
from data.db import get_db
from api.v1.dependencies import get_current_user
from domain.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])

async def get_user_repository(db: AsyncSession = Depends(get_db)) -> SQLUserRepository:
    return SQLUserRepository(db)

@router.post("/login", response_model=AuthResponse)
async def login(
    request: AuthRequest, 
    user_repo: SQLUserRepository = Depends(get_user_repository)
) -> AuthResponse:
    try:
        user_use_case = AuthenticateUser(user_repo)
        user = await user_use_case.execute(email=request.email, google_id=request.google_id)
        
        # Generate real JWT token
        token = create_access_token(data={"sub": str(user.id), "email": user.email})
        
        return AuthResponse(
            user_id=str(user.id),
            email=user.email,
            token=token,
            google_id=user.google_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

@router.get("/me", response_model=UserInfo)
async def get_me(
    current_user: User = Depends(get_current_user)
) -> UserInfo:
    return UserInfo(
        user_id=str(current_user.id),
        email=current_user.email,
        google_id=current_user.google_id
    )

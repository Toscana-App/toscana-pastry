
from fastapi import APIRouter, Depends, HTTPException, status
from domain.use_cases.authenticate_user import AuthenticateUser
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.schemas import AuthRequest, AuthResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["authentication"])

# Mocked session generator for testing purposes
async def get_session():
    # In a real app, this would be the actual session provider
    pass

async def get_user_repository(session: AsyncSession = Depends(get_session)) -> SQLUserRepository:
    return SQLUserRepository(session)

@router.post("/login", response_model=AuthResponse)
async def login(
    request: AuthRequest, 
    user_repo: SQLUserRepository = Depends(get_user_repository)
) -> AuthResponse:
    try:
        user_use_case = AuthenticateUser(user_repo)
        user = await user_use_case.execute(email=request.email, google_id=request.google_id)
        return AuthResponse(
            user_id=str(user.id),
            email=user.email,
            google_id=user.google_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

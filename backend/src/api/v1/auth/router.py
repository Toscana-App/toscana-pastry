from fastapi import APIRouter, Depends, HTTPException, status, Header
from domain.use_cases.authenticate_user import AuthenticateUser
from data.repositories.sql_user_repository import SQLUserRepository
from api.v1.auth.schemas import AuthRequest, AuthResponse
from core.config import settings
from domain.auth.logic import create_access_token, decode_access_token
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

@router.get("/me", response_model=AuthResponse)
async def get_me(
    authorization: str = Header(None),
    user_repo: SQLUserRepository = Depends(get_user_repository)
) -> AuthResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token")
    
    token = authorization.split(" ")[1]
    
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token payload")
        
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return AuthResponse(
            user_id=str(user.id),
            email=user.email,
            token=token,
            google_id=user.google_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal error")

from fastapi import APIRouter, Depends, HTTPException, status
from domain.models import User
from domain.repositories import UserRepository
from domain.use_cases import AuthenticateUser
from api.v1.dependencies import get_current_user
from api.v1.auth.dependencies import get_user_repository
from api.v1.auth.schemas import AuthRequest, AuthResponse, UserInfo
from domain.auth.logic import create_access_token, create_refresh_token, decode_refresh_token
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/login", response_model=AuthResponse)
async def login(request: AuthRequest, user_repo: UserRepository = Depends(get_user_repository)):
    user_use_case = AuthenticateUser(user_repo)
    try:
        user = await user_use_case.execute(email=request.email, google_id=request.google_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    return AuthResponse(
        user_id=str(user.id),
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token,
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

@router.post("/refresh")
async def refresh_token(request: RefreshRequest):
    try:
        payload = decode_refresh_token(request.refresh_token)
        user_id = payload["sub"]
        
        # Generate new access token
        # Note: In a production app, we would check if the refresh token is revoked
        new_access_token = create_access_token({"sub": user_id})
        
        return {"access_token": new_access_token}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

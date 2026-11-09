from pydantic import BaseModel, EmailStr
from typing import Optional
from domain.models import UserRole

class AuthRequest(BaseModel):
    email: Optional[EmailStr] = None
    google_id: Optional[str] = None

class AuthResponse(BaseModel):
    user_id: str
    email: str
    role: UserRole
    google_id: Optional[str] = None

class UserInfo(BaseModel):
    user_id: str
    email: str
    role: UserRole
    google_id: Optional[str] = None

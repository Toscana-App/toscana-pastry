from pydantic import BaseModel, EmailStr
from typing import Optional

class AuthRequest(BaseModel):
    email: Optional[EmailStr] = None
    google_id: Optional[str] = None

class AuthResponse(BaseModel):
    user_id: str
    email: str
    token: str
    google_id: Optional[str] = None

class UserInfo(BaseModel):
    user_id: str
    email: str
    google_id: Optional[str] = None

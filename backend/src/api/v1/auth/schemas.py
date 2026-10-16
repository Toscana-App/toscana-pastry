from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class AuthRequest(BaseModel):
    email: Optional[EmailStr] = None
    google_id: Optional[str] = Field(None, min_length=1)

class AuthResponse(BaseModel):
    user_id: str
    email: str
    token: str
    google_id: Optional[str]

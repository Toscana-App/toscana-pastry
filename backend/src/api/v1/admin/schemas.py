from typing import List, Optional
from pydantic import BaseModel
from domain.models import UserRole


class AdminUserItem(BaseModel):
    user_id: str
    email: str
    role: UserRole
    google_id: Optional[str] = None


class UserListResponse(BaseModel):
    total: int
    users: List[AdminUserItem]

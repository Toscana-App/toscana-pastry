from dataclasses import dataclass
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"

@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: UserRole = UserRole.CUSTOMER
    google_id: Optional[str] = None

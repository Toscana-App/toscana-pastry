import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"


@dataclass(frozen=True)
class User:
    """Entidad de dominio. La identidad la genera el propio dominio: quien crea
    un User no necesita conocer ni construir el id."""

    email: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: UserRole = UserRole.CUSTOMER
    google_id: Optional[str] = None

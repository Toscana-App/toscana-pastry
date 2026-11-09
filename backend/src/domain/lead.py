
import uuid
from dataclasses import dataclass, field
from typing import Literal

ALLOWED_CUSTOMER_TYPES = ("consumer", "business")


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


@dataclass(frozen=True)
class Lead:

    name: str
    email: str
    customer_type: Literal["consumer", "business"]
    message: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phone: str | None = None
    business_name: str | None = None
    location: str | None = None
    read: bool = False

    def __post_init__(self):
        object.__setattr__(self, "name", _strip(self.name))
        object.__setattr__(self, "email", _strip(self.email))
        object.__setattr__(self, "message", _strip(self.message))

        if not self.name:
            raise ValueError("name requerido y no puede ser solo espacios")
        if not self.email:
            raise ValueError("email requerido y no puede ser solo espacios")
        if not self.message:
            raise ValueError("message requerido y no puede ser solo espacios")

        if self.customer_type not in ALLOWED_CUSTOMER_TYPES:
            raise ValueError(
                f"customer_type invalido: {self.customer_type!r} "
                f"(permitido: {ALLOWED_CUSTOMER_TYPES})"
            )

        if self.customer_type == "business" and not self.business_name:
            raise ValueError("customer_type=business requiere business_name")

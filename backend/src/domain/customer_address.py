"""Dominio del libro de direcciones por cliente (RF-P11-09, C2).

Entidad frozen con __post_init__ para validacion de campos. Reglas de
invariant:
- MAX_ADDRESSES_PER_CUSTOMER direcciones por cliente.
- Exactamente una direccion default por cliente (la primera creada pasa
  a default; al borrar la default, la mas antigua restante la hereda).
"""
import datetime
import uuid
from dataclasses import dataclass, field

MAX_ADDRESSES_PER_CUSTOMER = 5

# String length limits (RF-P11-09)
MAX_STREET_LINE_1 = 120
MAX_STREET_LINE_2 = 120
MAX_CITY = 120
MAX_POSTAL_CODE = 20
MAX_PROVINCE = 120
MAX_PHONE = 30


@dataclass(frozen=True)
class CustomerAddress:
    """Direccion de entrega de un cliente (RF-P11-09)."""

    street_line_1: str
    street_line_2: str | None = None
    city: str | None = None
    postal_code: str | None = None
    province: str | None = None
    phone: str | None = None
    is_default: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def __post_init__(self):
        street_line_1 = self.street_line_1.strip()
        if not street_line_1:
            raise ValueError(
                "street_line_1 requerido y no puede ser solo espacios"
            )
        if len(street_line_1) > MAX_STREET_LINE_1:
            raise ValueError(
                f"street_line_1 maximo {MAX_STREET_LINE_1}: {len(street_line_1)}"
            )
        if self.street_line_2 is not None and len(self.street_line_2) > MAX_STREET_LINE_2:
            raise ValueError(
                f"street_line_2 maximo {MAX_STREET_LINE_2}: {len(self.street_line_2)}"
            )
        if self.city is not None and len(self.city) > MAX_CITY:
            raise ValueError(f"city maximo {MAX_CITY}: {len(self.city)}")
        if self.postal_code is not None and len(self.postal_code) > MAX_POSTAL_CODE:
            raise ValueError(
                f"postal_code maximo {MAX_POSTAL_CODE}: {len(self.postal_code)}"
            )
        if self.province is not None and len(self.province) > MAX_PROVINCE:
            raise ValueError(
                f"province maximo {MAX_PROVINCE}: {len(self.province)}"
            )
        if self.phone is not None and len(self.phone) > MAX_PHONE:
            raise ValueError(f"phone maximo {MAX_PHONE}: {len(self.phone)}")

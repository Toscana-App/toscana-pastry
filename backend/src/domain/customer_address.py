import datetime
import uuid
from dataclasses import dataclass, field, replace

MAX_ADDRESSES_PER_CUSTOMER = 5

MAX_STREET_LINE_1 = 120
MAX_STREET_LINE_2 = 120
MAX_CITY = 120
MAX_POSTAL_CODE = 20
MAX_PROVINCE = 120
MAX_PHONE = 30


@dataclass(frozen=True)
class CustomerAddress:

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


class AddressBookError(ValueError):
    pass


class AddressLimitExceeded(AddressBookError):
    pass


class CannotUnsetDefault(AddressBookError):
    pass


class CannotRemoveOnlyAddress(AddressBookError):
    pass


def add_address(
    existing: list[CustomerAddress], new: CustomerAddress
) -> CustomerAddress:
    if len(existing) >= MAX_ADDRESSES_PER_CUSTOMER:
        raise AddressLimitExceeded(
            f"Maximo {MAX_ADDRESSES_PER_CUSTOMER} direcciones por cliente"
        )
    return replace(new, is_default=len(existing) == 0)


def apply_changes(
    address: CustomerAddress, changes: dict, *, set_default: bool | None = None
) -> CustomerAddress:
    if set_default is False and address.is_default:
        raise CannotUnsetDefault(
            "No se puede quitar el default: debe existir exactamente una"
        )
    return replace(
        address, **changes, is_default=address.is_default or set_default is True
    )


def default_to_demote(
    addresses: list[CustomerAddress], promoted_id: str
) -> list[str]:
    return [a.id for a in addresses if a.is_default and a.id != promoted_id]


def remove_address(
    addresses: list[CustomerAddress], address_id: str
) -> str | None:
    if len(addresses) <= 1:
        raise CannotRemoveOnlyAddress(
            "No se puede borrar la unica direccion del cliente"
        )
    target = next((a for a in addresses if a.id == address_id), None)
    if target is None or not target.is_default:
        return None
    return next(a.id for a in addresses if a.id != address_id)

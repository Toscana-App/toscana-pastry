from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_STREET_LINE_1 = 120
MAX_STREET_LINE_2 = 120
MAX_CITY = 120
MAX_POSTAL_CODE = 20
MAX_PROVINCE = 120
MAX_PHONE = 30


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class AddressCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    street_line_1: str = Field(min_length=1, max_length=MAX_STREET_LINE_1)
    street_line_2: str | None = Field(default=None, max_length=MAX_STREET_LINE_2)
    city: str | None = Field(default=None, max_length=MAX_CITY)
    postal_code: str | None = Field(default=None, max_length=MAX_POSTAL_CODE)
    province: str | None = Field(default=None, max_length=MAX_PROVINCE)
    phone: str | None = Field(default=None, max_length=MAX_PHONE)

    @field_validator("street_line_1")
    @classmethod
    def _street_line_1_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("street_line_1 no puede estar vacio")
        return value.strip()

    @field_validator("street_line_2", "city", "postal_code", "province", "phone")
    @classmethod
    def _strip_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AddressUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    street_line_1: str | None = Field(
        default=None, min_length=1, max_length=MAX_STREET_LINE_1
    )
    street_line_2: str | None = Field(default=None, max_length=MAX_STREET_LINE_2)
    city: str | None = Field(default=None, max_length=MAX_CITY)
    postal_code: str | None = Field(default=None, max_length=MAX_POSTAL_CODE)
    province: str | None = Field(default=None, max_length=MAX_PROVINCE)
    phone: str | None = Field(default=None, max_length=MAX_PHONE)
    is_default: bool | None = None

    @field_validator("street_line_1")
    @classmethod
    def _street_line_1_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("street_line_1 no puede estar vacio")
        return value.strip() if value is not None else None

    @field_validator("street_line_2", "city", "postal_code", "province", "phone")
    @classmethod
    def _strip_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AddressResponse(BaseModel):

    id: str
    street_line_1: str
    street_line_2: str | None = None
    city: str | None = None
    postal_code: str | None = None
    province: str | None = None
    phone: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AddressEnvelope(BaseModel):

    address: AddressResponse


class AddressListResponse(BaseModel):

    items: list[AddressResponse]


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=30)
    delivery_address: str | None = Field(default=None, max_length=500)

    @field_validator("delivery_address")
    @classmethod
    def _strip_address(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CustomerUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    delivery_address: str | None = Field(default=None, max_length=500)

    @field_validator("delivery_address")
    @classmethod
    def _strip_address(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    delivery_address: str | None = None
    created_at: str


class CustomerListResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int

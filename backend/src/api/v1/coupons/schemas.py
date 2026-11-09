from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.v1.money import Qty
from domain.coupon import MAX_COUPON_CODE

COUPON_TYPES = Literal["percent", "fixed"]
COUPON_STATUSES = Literal["active", "paused"]


class CouponCreate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=MAX_COUPON_CODE)
    type: COUPON_TYPES
    value: Qty = Field(ge=Decimal("0"))
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    status: COUPON_STATUSES = "active"

    @field_validator("code")
    @classmethod
    def _code_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code no puede estar vacio")
        return value.strip()


class CouponUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(
        default=None, min_length=1, max_length=MAX_COUPON_CODE
    )
    type: COUPON_TYPES | None = None
    value: Qty | None = Field(default=None, ge=Decimal("0"))
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    status: COUPON_STATUSES | None = None

    @field_validator("code")
    @classmethod
    def _code_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("code no puede estar vacio")
        return value.strip() if value is not None else None


class CouponResponse(BaseModel):

    id: str
    code: str
    type: str
    value: Qty
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = None
    uses: int
    status: str
    created_at: datetime
    updated_at: datetime


class CouponEnvelope(BaseModel):

    coupon: CouponResponse


class CouponListResponse(BaseModel):

    items: list[CouponResponse]
    total: int
    page: int
    page_size: int

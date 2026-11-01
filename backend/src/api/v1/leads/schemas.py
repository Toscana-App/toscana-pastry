"""Lead API schemas (RF-P11-13, C5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LeadCreateRequest(BaseModel):
    """Public POST /leads request body."""

    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=320)
    customer_type: str = Field(..., pattern="^(consumer|business)$")
    message: str = Field(..., min_length=1, max_length=2000)
    phone: str | None = Field(default=None, max_length=50)
    business_name: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=300)


class LeadResponse(BaseModel):
    """Lead detail response."""

    id: str
    name: str
    email: str
    customer_type: str
    message: str
    phone: str | None = None
    business_name: str | None = None
    location: str | None = None
    read: bool = False
    created_at: datetime


class LeadListResponse(BaseModel):
    """Paginated lead list for admin."""

    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


class LeadReadPatch(BaseModel):
    """PATCH /leads/{id}/read body."""

    read: bool


class LeadReadAllResponse(BaseModel):
    """POST /leads/read-all response."""

    updated: int

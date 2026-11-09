
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SendResponse(BaseModel):

    id: str
    provider: str
    status: str
    reference_kind: str
    reference_id: str
    sent_at: datetime
    message_id: str | None = None
    failed_reason: str | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None


class SendListResponse(BaseModel):

    items: list[SendResponse]
    total: int
    page: int
    page_size: int


class SendStatsResponse(BaseModel):

    total: int
    sent: int
    delivered: int
    read: int
    failed: int
    read_rate: float


class ResendResponse(BaseModel):

    send: SendResponse


class ResendBudgetDetail(BaseModel):

    code: str = "whatsapp_budget_exceeded"
    limit: int = 500
    retry_after: str = Field(description="Dia sugerido para reintentar (ISO 8601)")

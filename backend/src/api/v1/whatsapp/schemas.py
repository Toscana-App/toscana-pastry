"""WhatsApp sends API schemas (RF-P10-07/08, C7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SendResponse(BaseModel):
    """Un envio con su estado actual."""

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
    """Paginated sends list (owner)."""

    items: list[SendResponse]
    total: int
    page: int
    page_size: int


class SendStatsResponse(BaseModel):
    """Métricas de envios (ventana 30 dias)."""

    total: int
    sent: int
    delivered: int
    read: int
    failed: int
    read_rate: float


class ResendResponse(BaseModel):
    """Respuesta de POST /sends/{id}/resend."""

    send: SendResponse


class ResendBudgetDetail(BaseModel):
    """Detalle del 429 por budget (RNF-P10-06)."""

    code: str = "whatsapp_budget_exceeded"
    limit: int = 500
    retry_after: str = Field(description="Dia sugerido para reintentar (ISO 8601)")

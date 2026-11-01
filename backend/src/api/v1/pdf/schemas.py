from pydantic import BaseModel


class PdfShareResponse(BaseModel):
    """POST /budgets/{id}/pdf (P9): link firmado temporal (72 h)."""

    url: str
    expires_at: str  # ISO 8601 UTC

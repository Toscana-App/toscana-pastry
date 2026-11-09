from pydantic import BaseModel


class PdfShareResponse(BaseModel):

    url: str
    expires_at: str

"""Esquemas (respuestas) de la API de importacion CSV (T-CSV-2/4)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ImportUploadResponse(BaseModel):
    """201 al subir: import_id + totales + primeras filas con error."""

    import_id: str
    entity: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    first_errors: list[list[str]]


class ImportRowOut(BaseModel):
    row_number: int
    status: str  # "valid" | "invalid"
    data: dict[str, Any]
    errors: list[str]


class ImportSessionOut(BaseModel):
    import_id: str
    entity: str
    status: str
    filename: str
    delimiter: str
    encoding: str
    template_columns: list[str]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created_at: datetime
    confirmed_at: datetime | None = None


class ImportRowsResponse(BaseModel):
    """GET /imports/{id}/rows: sesion + pagina de filas."""

    session: ImportSessionOut
    rows: list[ImportRowOut]
    total: int


class ConfirmResponse(BaseModel):
    import_id: str
    status: str
    created: int
    skipped: int
    message: str = ""


class DiscardResponse(BaseModel):
    import_id: str
    status: str

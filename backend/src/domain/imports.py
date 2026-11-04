"""Dominio de la importacion CSV con staging (RF-CSV-01/02/07/10/11).

Capa pura: sin I/O. Aqui se modelan la sesion de importacion, sus filas y la
regla de negocio de coincidencia exacta de columnas. El parsing del archivo
(encoding, separador) vive en ``api.v1.imports.parsers`` y la persistencia en
``data.repositories.sql_import_repository``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Mapping, Sequence

# RF-CSV-07: TTL de la tabla de staging (7 dias).
STAGING_TTL = timedelta(days=7)


class ImportStatus(str, Enum):
    """Estado del ciclo de vida de una importacion (RF-CSV-05/06/07)."""

    RECEIVED = "received"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class ImportRowStatus(str, Enum):
    """Estado de una fila estadiada (RF-CSV-03)."""

    VALID = "valid"
    INVALID = "invalid"


class ColumnMismatchError(ValueError):
    """El set de columnas del CSV no coincide con la plantilla (RF-CSV-02/13).

    Lleva las columnas faltantes y las sobrantes para armar el 422 sin crear
    ``import_id`` ni staging (el archivo completo se rechaza).
    """

    def __init__(self, missing: Sequence[str], extra: Sequence[str]):
        self.missing = list(missing)
        self.extra = list(extra)
        super().__init__(
            "El archivo no coincide con la plantilla: faltan "
            f"{self.missing} y sobran {self.extra}"
        )


def check_columns(
    template_columns: Sequence[str], file_columns: Sequence[str]
) -> None:
    """Valida que el set de columnas del archivo sea IDENTICO al de la
    plantilla.

    El orden no importa (RF-CSV-02). Una columna ajena o faltante levanta
    :class:`ColumnMismatchError` con el listado de las columnas en falta (y las
    sobrantes).
    """
    file_set = set(file_columns)
    missing = [c for c in template_columns if c not in file_set]
    extra = [c for c in file_columns if c not in set(template_columns)]
    if missing or extra:
        raise ColumnMismatchError(missing, extra)


@dataclass
class ImportRow:
    """Una fila del CSV ya estadiada (RF-CSV-03)."""

    row_number: int
    status: ImportRowStatus
    data: Mapping[str, Any]
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportSession:
    """Sesion de importacion: metadatos + totales (RF-CSV-01/04)."""

    id: str
    tenant_id: str
    user_id: str
    entity: str
    status: ImportStatus
    filename: str
    delimiter: str
    encoding: str
    template_columns: list[str]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created_at: datetime
    confirmed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        tenant_id: str,
        user_id: str,
        entity: str,
        filename: str,
        delimiter: str,
        encoding: str,
        template_columns: Sequence[str],
        total_rows: int,
        valid_rows: int,
    ) -> "ImportSession":
        return cls(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            entity=entity,
            status=ImportStatus.RECEIVED,
            filename=filename,
            delimiter=delimiter,
            encoding=encoding,
            template_columns=list(template_columns),
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_rows=total_rows - valid_rows,
            created_at=datetime.now(UTC),
            confirmed_at=None,
        )

    def totals(self) -> tuple[int, int, int]:
        """(total, validas, invalidas)."""
        return (self.total_rows, self.valid_rows, self.invalid_rows)

    def is_expired(self, now: datetime) -> bool:
        """RF-CSV-07: la sesion expira a los 7 dias de creada."""
        return now - self.created_at > STAGING_TTL

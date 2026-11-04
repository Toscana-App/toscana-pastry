"""Dependencias de la API de importacion CSV (T-CSV-3)."""
from __future__ import annotations

from fastapi import HTTPException, status

from api.v1.imports.adapters import ADAPTERS, ENTITIES
from api.v1.imports.adapters.base import ImportAdapter


def resolve_adapter(entity: str) -> ImportAdapter:
    """Devuelve el adapter de la entidad o 422 si es desconocida.

    El 422 incluye el listado de entidades validas (sin jerga).
    """
    adapter = ADAPTERS.get(entity)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": f"Entidad desconocida: '{entity}'.",
                "entities": ENTITIES,
            },
        )
    return adapter

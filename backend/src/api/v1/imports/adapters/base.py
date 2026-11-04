"""Contrato de un adapter de importacion (T-CSV-3/5/6/7).

Un adapter une una entidad con el flujo generico de /imports. Define:

- ``columns``: las columnas de la plantilla. Son el *mismo* modelo que valida
  (RF-CSV-04): la plantilla se genera a partir de ``columns`` + ``example_rows``
  y ``validate_row`` valida contra el mismo set. Nunca se desincronizan.
- ``validate_row``: valida una fila (funcion pura) y devuelve los datos
  normalizados (listos para insertar) + los errores en espanol (sin jerga).
- ``find_duplicate`` / ``insert``: aplicacion al confirmar (async, sobre la
  transaccion unica del confirm; el commit lo hace el confirm, no el adapter).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession


class ImportAdapter(ABC):
    #: nombre corto de la entidad (valor de ``?entity=`` y de ImportSession.entity).
    entity: str = ""

    #: si False, el confirm marca la sesion sin insertar registros (v1:
    #: productos planos requieren receta). El router usa esto para el mensaje.
    inserts_on_confirm: bool = True

    #: mensaje que devuelve el confirm cuando ``inserts_on_confirm`` es False.
    confirm_message: str = ""

    #: filas de ejemplo (>= 2) que van en la plantilla; deben pasar la validacion.
    example_rows: Sequence[dict[str, str]] = ()

    @property
    @abstractmethod
    def columns(self) -> list[str]:
        """Columnas de la plantilla (el mismo modelo que valida, RF-CSV-04)."""

    def template(self) -> str:
        """CSV de plantilla: encabezado + filas de ejemplo (RF-CSV-01)."""
        header = ";".join(self.columns)
        lines = [header]
        for example in self.example_rows:
            lines.append(";".join(str(example.get(col, "")) for col in self.columns))
        return "\n".join(lines) + "\n"

    @abstractmethod
    def validate_row(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        """Valida una fila (pura). Devuelve (datos_normalizados, errores)."""

    @abstractmethod
    async def find_duplicate(
        self, session: AsyncSession, data: dict[str, Any]
    ) -> str | None:
        """Nombre del registro existente si es duplicado; None si no lo es."""

    @abstractmethod
    async def insert(self, session: AsyncSession, data: dict[str, Any]) -> None:
        """Inserta el registro confirmado (session.add; el commit es del confirm)."""

"""Schemas de la ventana de pedidos (corte de pedidos).

La ventana controla si el portal acepta pedidos nuevos (RF-P5-07):
cerrada, el portal responde 409 con el mensaje y el admin ve el banner
con la fecha de reapertura (RF-P6-09).
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderWindowResponse(BaseModel):
    """Estado de la ventana de pedidos (GET)."""

    model_config = ConfigDict(extra="forbid")

    open: bool
    reopens_at: Optional[dt.datetime]
    message: str


class OrderWindowUpdate(BaseModel):
    """Actualización de la ventana de pedidos (PATCH).

    `open` es requerido. `reopens_at` es obligatorio al cerrar
    (open=false) y se ignora al abrir (open=true: se fuerza a nulo).
    `message` limita 200 caracteres (lo que muestra el portal y el
    banner admin).
    """

    model_config = ConfigDict(extra="forbid")

    open: bool
    reopens_at: Optional[dt.datetime] = None
    message: str = Field(default="", max_length=200)

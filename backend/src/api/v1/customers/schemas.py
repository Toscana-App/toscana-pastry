"""Schemas Pydantic de la API de clientes (Fase 6, P6).

El cliente es nombre + telefono (sin email: el canal es WhatsApp,
RF-P6-06). La dedup por (nombre, telefono) la hace el repositorio
(RF-P6-08): crear un duplicado devuelve al existente con 409."""
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from api.v1.money import Money


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=30)


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    created_at: str


class CustomerListResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int

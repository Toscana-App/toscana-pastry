from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.imports.adapters.base import ImportAdapter
from data.models import CustomerORM
from domain.orders import normalize_customer_name, normalize_phone

MIN_NAME, MAX_NAME = 2, 120
MIN_PHONE, MAX_PHONE = 5, 20


class CustomerRow(BaseModel):

    nombre: str = ""
    telefono: str = ""


class CustomersAdapter(ImportAdapter):
    entity = "customers"
    example_rows = [
        {"nombre": "María González", "telefono": "11 5555-0101"},
        {"nombre": "Pedro López", "telefono": "11-5555-0202"},
    ]

    @property
    def columns(self) -> list[str]:
        return list(CustomerRow.model_fields.keys())

    def validate_row(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        name = row.get("nombre", "").strip()
        phone_raw = row.get("telefono", "").strip()

        if not name:
            errors.append("nombre: falta el nombre")
        elif len(name) < MIN_NAME or len(name) > MAX_NAME:
            errors.append(f"nombre: debe tener entre {MIN_NAME} y {MAX_NAME} caracteres")

        phone = ""
        if not phone_raw:
            errors.append("teléfono: falta el teléfono")
        else:
            try:
                phone = normalize_phone(phone_raw)
            except ValueError:
                errors.append("teléfono: debe contener dígitos")
            else:
                if not (MIN_PHONE <= len(phone) <= MAX_PHONE):
                    errors.append(
                        f"teléfono: debe tener entre {MIN_PHONE} y {MAX_PHONE} dígitos"
                    )

        data: dict[str, Any] = {
            "name": name,
            "phone": phone,
            "name_norm": normalize_customer_name(name) if name else "",
            "phone_norm": phone,
        }
        return data, errors

    async def find_duplicate(
        self, session: AsyncSession, data: dict[str, Any]
    ) -> str | None:
        if not data.get("name") or not data.get("phone"):
            return None
        result = await session.execute(
            select(CustomerORM.name)
            .where(
                CustomerORM.name_norm == data["name_norm"],
                CustomerORM.phone_norm == data["phone_norm"],
            )
            .limit(1)
        )
        return result.scalars().first()

    async def insert(self, session: AsyncSession, data: dict[str, Any]) -> None:
        session.add(
            CustomerORM(
                id=str(uuid.uuid4()),
                name=data["name"],
                phone=data["phone"],
                name_norm=data["name_norm"],
                phone_norm=data["phone_norm"],
                created_at=datetime.now(UTC),
            )
        )

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.imports.adapters.base import ImportAdapter
from api.v1.money import cents_to_decimal, decimal_to_cents
from data.accent import accent_fold
from data.models import IngredientORM, StockMovementORM
from domain.ingredients_import import _to_decimal
from domain.models import STOCK_UNITS

MAX_NAME = 120
_UNIT_CANONICAL = {unit.lower(): unit for unit in STOCK_UNITS}


class IngredientRow(BaseModel):

    nombre: str = ""
    cantidad: str = ""
    unidad: str = ""
    precio: str = ""


class IngredientsAdapter(ImportAdapter):
    entity = "ingredients"
    example_rows = [
        {"nombre": "Harina 000", "cantidad": "1", "unidad": "kg", "precio": "1200"},
        {"nombre": "Leche entera", "cantidad": "2", "unidad": "L", "precio": "1500"},
    ]

    @property
    def columns(self) -> list[str]:
        return list(IngredientRow.model_fields.keys())

    def validate_row(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        name = row.get("nombre", "").strip()
        unit_raw = row.get("unidad", "").strip()
        price_raw = row.get("precio", "").strip()
        qty_raw = row.get("cantidad", "").strip()

        if not name:
            errors.append("nombre: falta el nombre")
        elif len(name) > MAX_NAME:
            errors.append(f"nombre: máximo de {MAX_NAME} caracteres")

        unit = "unidad"
        if unit_raw:
            canonical = _UNIT_CANONICAL.get(unit_raw.lower())
            if canonical is None:
                errors.append(
                    f"unidad: '{unit_raw}' no es válida (usá {'/'.join(STOCK_UNITS)})"
                )
            else:
                unit = canonical

        price_cents: int | None = None
        if not price_raw:
            errors.append("precio: falta el precio")
        else:
            try:
                price_cents = decimal_to_cents(_to_decimal(price_raw, "precio"))
            except (ValueError, ArithmeticError):
                errors.append(f"precio: '{price_raw}' no es un número válido")

        qty = Decimal("0")
        if qty_raw:
            try:
                qty = _to_decimal(qty_raw, "cantidad")
            except (ValueError, ArithmeticError):
                errors.append(f"cantidad: '{qty_raw}' no es un número válido")

        data: dict[str, Any] = {
            "name": name,
            "unit": unit,
            "price_per_unit_cents": price_cents,
            "stock_qty": str(qty),
        }
        return data, errors

    async def find_duplicate(
        self, session: AsyncSession, data: dict[str, Any]
    ) -> str | None:
        name = data.get("name", "")
        if not name:
            return None
        folded = accent_fold(name)
        result = await session.execute(
            select(IngredientORM.name)
            .where(func.accent_fold(IngredientORM.name) == folded)
            .limit(1)
        )
        return result.scalars().first()

    async def insert(self, session: AsyncSession, data: dict[str, Any]) -> None:
        ingredient_id = str(uuid.uuid4())
        price_per_unit = cents_to_decimal(data["price_per_unit_cents"])
        session.add(
            IngredientORM(
                id=ingredient_id,
                name=data["name"],
                unit=data["unit"],
                price_per_unit=str(price_per_unit),
                stock_qty=data["stock_qty"],
                low_stock_threshold="0",
            )
        )
        try:
            qty = Decimal(data["stock_qty"])
        except InvalidOperation:
            qty = Decimal("0")
        if qty > 0:
            session.add(
                StockMovementORM(
                    id=str(uuid.uuid4()),
                    ingredient_id=ingredient_id,
                    qty_delta=data["stock_qty"],
                    reason="compra",
                    ref="inicial",
                    created_at=datetime.now(UTC),
                )
            )

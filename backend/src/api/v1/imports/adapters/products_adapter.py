"""Adapter de productos (T-CSV-6, RF-CSV-09, RNF-CSV-06).

Columnas (plan): nombre, categoría, unidad, costo unitario, precio venta,
stock inicial.

DECISIÓN v1 (documentada en el PR): el dominio ``Product`` no persiste
costo/precio/stock/unidad y exige una receta con al menos un insumo
(``domain.models.Product.__post_init__``). Un CSV plano de 6 columnas no puede
crear un producto cargable (``sql_product_repository.list`` usa ``_to_domain``
que requiere receta). Por eso el adapter valida/estadia/previsualiza las 6
columnas (el flujo UI completo funciona) pero el confirm NO inserta registros:
marca la sesion como confirmada con un mensaje claro (``inserts_on_confirm``
False). Cuando el modelo de producto soporte datos planos, basta con activar
los inserts sin tocar el flujo.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.imports.adapters.base import ImportAdapter
from data.accent import accent_fold
from data.models import ProductORM
from domain.ingredients_import import _to_decimal

MAX_NAME = 120
MAX_CATEGORY = 60
_NUMERIC_COLUMNS = (
    ("costo unitario", "costo_unitario"),
    ("precio venta", "precio_venta"),
    ("stock inicial", "stock_inicial"),
)


class ProductRow(BaseModel):
    """Fuente de las columnas de la plantilla (RF-CSV-04). Valores como string
    (el CSV es texto); la validacion los normaliza."""

    nombre: str = ""
    categoria: str = ""
    unidad: str = ""
    costo_unitario: str = ""
    precio_venta: str = ""
    stock_inicial: str = ""


class ProductsAdapter(ImportAdapter):
    entity = "products"
    inserts_on_confirm = False
    confirm_message = (
        "v1: los productos importados no crean registros (el modelo de producto "
        "requiere receta). La importacion quedo confirmada sin registros."
    )
    example_rows = [
        {
            "nombre": "Torta de limón",
            "categoria": "Tortas",
            "unidad": "unidad",
            "costo_unitario": "3000",
            "precio_venta": "6000",
            "stock_inicial": "10",
        },
        {
            "nombre": "Factura",
            "categoria": "Facturas",
            "unidad": "unidad",
            "costo_unitario": "1200",
            "precio_venta": "2500",
            "stock_inicial": "20",
        },
    ]

    @property
    def columns(self) -> list[str]:
        return list(ProductRow.model_fields.keys())

    def validate_row(self, row: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
        errors: list[str] = []
        name = row.get("nombre", "").strip()
        category = row.get("categoria", "").strip()

        if not name:
            errors.append("nombre: falta el nombre")
        elif len(name) < 2:
            errors.append("nombre: debe tener al menos 2 caracteres")
        elif len(name) > MAX_NAME:
            errors.append(f"nombre: máximo de {MAX_NAME} caracteres")

        if not category:
            errors.append("categoría: falta la categoría")
        elif len(category) > MAX_CATEGORY:
            errors.append(f"categoría: máximo de {MAX_CATEGORY} caracteres")

        for label, key in _NUMERIC_COLUMNS:
            raw = row.get(key, "").strip()
            if raw:
                try:
                    value = _to_decimal(raw, label)
                except (ValueError, ArithmeticError):
                    errors.append(f"{label}: '{raw}' no es un número válido")
                else:
                    if value < 0:
                        errors.append(f"{label}: no puede ser negativo")

        data: dict[str, Any] = {
            "name": name,
            "category": category,
            "unit": row.get("unidad", "").strip(),
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
            select(ProductORM.name)
            .where(func.accent_fold(ProductORM.name) == folded)
            .limit(1)
        )
        return result.scalars().first()

    async def insert(self, session: AsyncSession, data: dict[str, Any]) -> None:
        # v1: no-op (ver el docstring del modulo).
        return None

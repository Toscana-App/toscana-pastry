"""Dependencies para los repositorios de la calculadora (RF-P5CC-08)."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from data.db import get_db
from data.repositories.calc.sql_calc_settings_repository import SQLCalcSettingsRepository
from data.repositories.calc.sql_calc_material_category_repository import (
    SQLCalcMaterialCategoryRepository,
)
from data.repositories.calc.sql_calc_material_repository import (
    SQLCalcMaterialRepository,
)
from data.repositories.calc.sql_calc_product_category_repository import (
    SQLCalcProductCategoryRepository,
)
from data.repositories.calc.sql_calc_supplier_repository import SQLCalcSupplierRepository
from data.repositories.calc.sql_calc_default_cost_repository import SQLCalcDefaultCostRepository


def get_calc_settings_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcSettingsRepository:
    return SQLCalcSettingsRepository(db)


def get_calc_material_category_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcMaterialCategoryRepository:
    return SQLCalcMaterialCategoryRepository(db)


def get_calc_product_category_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcProductCategoryRepository:
    return SQLCalcProductCategoryRepository(db)


def get_calc_supplier_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcSupplierRepository:
    return SQLCalcSupplierRepository(db)


def get_calc_default_cost_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcDefaultCostRepository:
    return SQLCalcDefaultCostRepository(db)


def get_calc_material_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLCalcMaterialRepository:
    return SQLCalcMaterialRepository(db)

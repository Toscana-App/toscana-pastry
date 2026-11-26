"""Base e2e throwaway + seed idempotente (ODD e2e-order-lifecycle, S3).

Reusa el engine/init_db/ORM de la app para que el esquema sea exactamente el
esquema de la app. IMPORTANTE: `run.py` setea `DATABASE_URL` antes de importar
este modulo (el engine de `data.db` se crea con ese env en el import).
"""

from __future__ import annotations

import os

import asyncpg
from sqlalchemy import select

from data.db import AsyncSessionLocal, engine, init_db
from data.models import (
    Base,
    IngredientORM,
    ProductORM,
    RecipeItemORM,
    UserORM,
)

E2E_DB = "toscana_e2e_db"
_PG_ADMIN_URL = os.getenv(
    "E2E_PG_ADMIN_URL", "postgresql://postgres:password@127.0.0.1:5432/postgres"
)

ADMIN_EMAIL = "admin.e2e@example.com"
ADMIN_GOOGLE_ID = "g-e2e-admin"
CUSTOMER_A_EMAIL = "clienteA.e2e@example.com"
CUSTOMER_A_GOOGLE_ID = "g-e2e-customer-a"
CUSTOMER_B_EMAIL = "clienteB.e2e@example.com"
CUSTOMER_B_GOOGLE_ID = "g-e2e-customer-b"

INGREDIENT_ID = "ing-e2e-1"
INGREDIENT_NAME = "Masa de panaderia e2e"
PRODUCT_ID = "prod-e2e-1"
PRODUCT_NAME = "Medialun e2e"


async def drop_database(name: str = E2E_DB) -> None:
    admin = await asyncpg.connect(_PG_ADMIN_URL)
    try:
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await admin.close()


async def ensure_database(name: str = E2E_DB) -> None:
    admin = await asyncpg.connect(_PG_ADMIN_URL)
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", name
        )
        if not exists:
            await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()


async def seed_all() -> None:
    """create_all + datos minimos. Idempotente (no duplica por nombre)."""
    await init_db(Base)
    async with AsyncSessionLocal() as session:
        for email, google_id, role in (
            (ADMIN_EMAIL, ADMIN_GOOGLE_ID, "admin"),
            (CUSTOMER_A_EMAIL, CUSTOMER_A_GOOGLE_ID, "customer"),
            (CUSTOMER_B_EMAIL, CUSTOMER_B_GOOGLE_ID, "customer"),
        ):
            result = await session.execute(
                select(UserORM).where(UserORM.email == email)
            )
            user = result.scalar_one_or_none()
            if user is None:
                session.add(
                    UserORM(id=f"u-{google_id}", email=email, google_id=google_id, role=role)
                )

        result = await session.execute(
            select(IngredientORM).where(
                IngredientORM.name == INGREDIENT_NAME,
                IngredientORM.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(
                IngredientORM(
                    id=INGREDIENT_ID,
                    name=INGREDIENT_NAME,
                    unit="unidad",
                    price_per_unit="250",
                    stock_qty="100",
                )
            )

        result = await session.execute(
            select(ProductORM).where(
                ProductORM.name == PRODUCT_NAME,
                ProductORM.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(
                ProductORM(
                    id=PRODUCT_ID,
                    name=PRODUCT_NAME,
                    category="panaderia",
                    description="Producto e2e",
                    available=True,
                )
            )
            session.add(
                RecipeItemORM(
                    id="ri-e2e-1",
                    product_id=PRODUCT_ID,
                    ingredient_id=INGREDIENT_ID,
                    qty="1",
                    unit="unidad",
                    position=0,
                )
            )
        await session.commit()
    await engine.dispose()

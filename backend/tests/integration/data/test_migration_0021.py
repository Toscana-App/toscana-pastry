import re
from pathlib import Path

import asyncpg
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from pg_support import URL

MIGRATION = (
    Path(__file__).resolve().parents[3] / "migrations" / "0021_orders_receipt.sql"
)

MIG_DB = "toscana_mig0021_test"

EXPECTED_COLUMNS = {
    "receipt_file",
    "receipt_content_type",
    "receipt_size_bytes",
    "receipt_uploaded_at",
    "receipt_viewed_at",
    "receipt_deleted_at",
}


def _upgrade_sql() -> str:
    script = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"-- Upgrade\s*(.*?)-- Downgrade", script, re.DOTALL)
    assert match is not None
    return match.group(1)


async def _create_migration_db() -> None:
    admin = await asyncpg.connect(
        user=URL.username,
        password=URL.password,
        host=URL.host,
        port=URL.port,
        database="postgres",
    )
    try:
        exists = await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", MIG_DB
        )
        if exists:
            await admin.execute(f'DROP DATABASE "{MIG_DB}"')
        await admin.execute(f'CREATE DATABASE "{MIG_DB}"')
    finally:
        await admin.close()


async def _drop_migration_db() -> None:
    admin = await asyncpg.connect(
        user=URL.username,
        password=URL.password,
        host=URL.host,
        port=URL.port,
        database="postgres",
    )
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{MIG_DB}"')
    finally:
        await admin.close()


@pytest_asyncio.fixture
async def migration_engine():
    await _create_migration_db()
    engine = create_async_engine(
        f"postgresql+asyncpg://{URL.username}:{URL.password}"
        f"@{URL.host}:{URL.port}/{MIG_DB}",
        poolclass=NullPool,
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE orders ("
                " id VARCHAR(36) PRIMARY KEY, "
                " customer_id VARCHAR(36) NOT NULL, "
                " status VARCHAR(32) NOT NULL, "
                " payment_method VARCHAR(32) NOT NULL"
                ")"
            )
        )
    try:
        yield engine
    finally:
        await engine.dispose()
        await _drop_migration_db()


async def _apply_upgrade(engine) -> None:
    upgrade = _upgrade_sql()
    async with engine.begin() as conn:
        for statement in filter(None, (s.strip() for s in upgrade.split(";"))):
            await conn.execute(text(statement))


async def _column_names(engine) -> set[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_schema = 'public' and table_name = 'orders'"
            )
        )
    return {row[0] for row in rows}


class TestMigration0021:

    async def test_adds_receipt_columns(self, migration_engine):
        await _apply_upgrade(migration_engine)
        assert EXPECTED_COLUMNS <= await _column_names(migration_engine)

    async def test_idempotent_second_run(self, migration_engine):
        await _apply_upgrade(migration_engine)
        await _apply_upgrade(migration_engine)
        assert EXPECTED_COLUMNS <= await _column_names(migration_engine)

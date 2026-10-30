"""Shared Postgres test database.

The suite runs against a dedicated `toscana_test` database inside the
docker-compose Postgres (`docker compose up -d`). The schema is rebuilt once
per session; every test starts from empty tables.
"""

import asyncio

import asyncpg
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from data.db import init_db
from data.models import Base
from pg_support import URL, make_test_engine


async def _create_database_if_missing() -> None:
    conn = await asyncpg.connect(
        user=URL.username,
        password=URL.password,
        host=URL.host,
        port=URL.port,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", URL.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{URL.database}"')
    finally:
        await conn.close()


async def _rebuild_schema() -> None:
    engine = make_test_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await init_db(Base, bind=engine)
    finally:
        await engine.dispose()


def pytest_sessionstart(session):
    asyncio.run(_create_database_if_missing())
    asyncio.run(_rebuild_schema())


@pytest_asyncio.fixture
async def db_session():
    engine = make_test_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()

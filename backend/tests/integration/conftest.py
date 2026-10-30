import pytest_asyncio
from sqlalchemy import text

from pg_support import make_test_engine
from data.models import Base


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    """Every integration test starts from empty tables."""
    engine = make_test_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    await engine.dispose()

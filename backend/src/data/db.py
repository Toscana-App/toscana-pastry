import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Postgres from docker-compose.yml is the only supported database. Override
# with DATABASE_URL for staging/production.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/toscana_db",
)

engine = create_async_engine(DATABASE_URL, echo=True)

# Accent/case-insensitive search (RF-P2-02): repositories call
# func.accent_fold(column). Postgres has no such function, so it is created
# from the unaccent extension at startup (see init_db).
_ACCENT_FOLD_DDL = (
    "CREATE EXTENSION IF NOT EXISTS unaccent",
    """
    CREATE OR REPLACE FUNCTION accent_fold(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$ SELECT lower(public.unaccent('public.unaccent', $1)) $$
    """,
)


async def init_db(base, bind=engine) -> None:
    """Create the accent_fold SQL function and the schema (idempotent)."""
    async with bind.begin() as conn:
        for statement in _ACCENT_FOLD_DDL:
            await conn.execute(text(statement))
        await conn.run_sync(base.metadata.create_all)


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from data.accent import accent_fold
from domain.repositories import UserRepository # for type hinting

DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(DATABASE_URL, echo=True)


@event.listens_for(engine.sync_engine, "connect")
def _register_sqlite_functions(dbapi_connection, connection_record):
    # Búsqueda insensible a acentos/mayúsculas (RF-P2-02): el repositorio
    # la usa vía func.accent_fold. En Postgres la reemplaza pg_trgm.
    dbapi_connection.create_function(
        "accent_fold", 1, accent_fold, deterministic=True
    )


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

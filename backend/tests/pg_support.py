
import os

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/toscana_test",
)
URL = make_url(TEST_DATABASE_URL)
assert URL.database and URL.database.endswith("_test"), (
    f"TEST_DATABASE_URL must target a *_test database, got {URL.database!r}"
)


def make_test_engine():
    return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

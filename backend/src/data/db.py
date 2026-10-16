
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from domain.repositories import UserRepository # for type hinting

DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

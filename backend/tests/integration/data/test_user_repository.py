
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from data.models import Base, UserORM
from domain.models import User
from data.repositories.sql_user_repository import SQLUserRepository
import datetime

@pytest_asyncio.fixture
async def user_repository(db_session):
    from data.repositories.sql_user_repository import SQLUserRepository
    return SQLUserRepository(db_session)

@pytest.mark.asyncio
async def test_save_and_get_user_by_email(user_repository: SQLUserRepository):
    user = User(email="test@example.com", google_id="google-123")
    await user_repository.save(user)
    
    found_user = await user_repository.get_by_email("test@example.com")
    assert found_user is not None
    assert found_user.email == "test@example.com"
    assert found_user.google_id == "google-123"

@pytest.mark.asyncio
async def test_get_user_by_google_id(user_repository: SQLUserRepository):
    user = User(email="test@example.com", google_id="google-123")
    await user_repository.save(user)
    
    found_user = await user_repository.get_by_google_id("google-123")
    assert found_user is not None
    assert found_user.email == "test@example.com"

@pytest.mark.asyncio
async def test_get_non_existent_user_returns_none(user_repository: SQLUserRepository):
    found_user = await user_repository.get_by_email("nonexistent@example.com")
    assert found_user is None

@pytest.mark.asyncio
async def test_get_non_existent_google_user_returns_none(user_repository: SQLUserRepository):
    found_user = await user_repository.get_by_google_id("no-google-id")
    assert found_user is None

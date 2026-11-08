"""Tests for UserRole.NEGOCIO and the enum persistence footgun fix (S4/S1)."""

import pytest
import pytest_asyncio
from sqlalchemy import text

from data.models import UserORM
from domain.models import User, UserRole
from data.repositories.sql_user_repository import SQLUserRepository


@pytest_asyncio.fixture
async def user_repository(db_session):
    return SQLUserRepository(db_session)


# ---- S1: NEGOCIO role exists and round-trips ----


@pytest.mark.asyncio
async def test_save_and_reload_negocio_role(user_repository: SQLUserRepository):
    """S1: UserRole.NEGOCIO persists and reloads correctly."""
    user = User(email="negocio@example.com", role=UserRole.NEGOCIO)
    await user_repository.save(user)

    found = await user_repository.get_by_email("negocio@example.com")
    assert found is not None
    assert found.role == UserRole.NEGOCIO
    assert found.role.value == "negocio"


@pytest.mark.asyncio
async def test_get_all_by_role_negocio(user_repository: SQLUserRepository):
    """S1: get_all_by_role works for NEGOCIO."""
    await user_repository.save(
        User(id="n1", email="n1@example.com", role=UserRole.NEGOCIO)
    )
    await user_repository.save(
        User(id="a1", email="a1@example.com", role=UserRole.ADMIN)
    )

    negocios = await user_repository.get_all_by_role(UserRole.NEGOCIO)
    assert len(negocios) == 1
    assert negocios[0].email == "n1@example.com"


# ---- S4: legacy uppercase values don't explode ----


@pytest.mark.asyncio
async def test_legacy_uppercase_admin_does_not_explode(user_repository: SQLUserRepository):
    """S4: A row persisted with uppercase 'ADMIN' must not raise on read."""
    # Simulate legacy DB row with uppercase role name
    orm = UserORM(
        id="legacy-1",
        email="legacy@example.com",
        role="ADMIN",  # uppercase — the footgun
    )
    user_repository.session.add(orm)
    await user_repository.session.commit()

    # Should NOT raise LookupError / ValueError
    found = await user_repository.get_by_email("legacy@example.com")
    assert found is not None
    assert found.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_legacy_uppercase_customer_does_not_explode(user_repository: SQLUserRepository):
    """S4: A row persisted with uppercase 'CUSTOMER' must not raise on read."""
    orm = UserORM(
        id="legacy-2",
        email="legacy2@example.com",
        role="CUSTOMER",  # uppercase — the footgun
    )
    user_repository.session.add(orm)
    await user_repository.session.commit()

    found = await user_repository.get_by_email("legacy2@example.com")
    assert found is not None
    assert found.role == UserRole.CUSTOMER


# ---- S4: new role persists as lowercase value ----


@pytest.mark.asyncio
async def test_negocio_persists_as_lowercase_value(db_session):
    """S4: The DB stores the enum VALUE (lowercase), not the NAME (uppercase)."""
    user = User(id="n-test", email="ntest@example.com", role=UserRole.NEGOCIO)
    await SQLUserRepository(db_session).save(user)

    # Inspect the raw DB value
    raw = await db_session.execute(
        text("SELECT role FROM users WHERE email = :e"),
        {"e": "ntest@example.com"},
    )
    row = raw.scalar_one()
    assert row == "negocio", f"Expected 'negocio' but DB has {row!r}"

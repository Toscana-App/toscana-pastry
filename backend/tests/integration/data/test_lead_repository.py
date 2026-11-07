"""Integration tests for Lead repository (RF-P11-13, C5).

Covers CRUD + admin list with filters + mark read/mark all read.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from domain.lead import Lead
from data.repositories.sql_lead_repository import SQLLeadRepository


@pytest_asyncio.fixture
async def lead_repo(db_session):
    return SQLLeadRepository(db_session)


# ─── Create ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_consumer_lead(lead_repo: SQLLeadRepository):
    lead = Lead(
        name="Juan Perez",
        email="juan@example.com",
        customer_type="consumer",
        message="Quiero info de tortas",
    )
    result = await lead_repo.create(lead)
    assert result.id is not None
    assert result.name == "Juan Perez"
    assert result.read is False


@pytest.mark.asyncio
async def test_create_business_lead(lead_repo: SQLLeadRepository):
    lead = Lead(
        name="Empresa SA",
        email="contacto@empresa.com",
        customer_type="business",
        business_name="Empresa SA",
        message="Pedido mayorista",
    )
    result = await lead_repo.create(lead)
    assert result.business_name == "Empresa SA"


# ─── Get ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_existing_lead(lead_repo: SQLLeadRepository):
    lead = Lead(
        name="Test",
        email="test@example.com",
        customer_type="consumer",
        message="Hi",
    )
    created = await lead_repo.create(lead)

    found = await lead_repo.get(created.id)
    assert found is not None
    assert found.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_nonexistent_lead_returns_none(lead_repo: SQLLeadRepository):
    found = await lead_repo.get("nonexistent-id")
    assert found is None


# ─── List with filters ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_leads(lead_repo: SQLLeadRepository):
    for i in range(5):
        await lead_repo.create(
            Lead(
                name=f"User {i}",
                email=f"user{i}@example.com",
                customer_type="consumer",
                message="Hi",
            )
        )

    leads, total = await lead_repo.list(q=None, read=None, customer_type=None, page=1, page_size=20)
    assert len(leads) == 5
    assert total == 5


@pytest.mark.asyncio
async def test_list_filter_by_read_true(lead_repo: SQLLeadRepository):
    await lead_repo.create(
        Lead(name="A", email="a@b.com", customer_type="consumer", message="Hi")
    )
    await lead_repo.create(
        Lead(name="B", email="b@b.com", customer_type="consumer", message="Hi")
    )
    # Mark first as read
    first = await lead_repo.get((await lead_repo.list(None, None, None, 1, 20))[0][0].id)
    if first:
        await lead_repo.set_read(first.id, True)

    leads, total = await lead_repo.list(q=None, read=True, customer_type=None, page=1, page_size=20)
    assert total == 1


@pytest.mark.asyncio
async def test_list_filter_by_customer_type(lead_repo: SQLLeadRepository):
    await lead_repo.create(
        Lead(name="Consumer", email="c@b.com", customer_type="consumer", message="Hi")
    )
    await lead_repo.create(
        Lead(name="Business", email="biz@b.com", customer_type="business", business_name="Biz", message="Hi")
    )

    leads, total = await lead_repo.list(q=None, read=None, customer_type="business", page=1, page_size=20)
    assert total == 1
    assert leads[0].customer_type == "business"


@pytest.mark.asyncio
async def test_list_search_q_in_name(lead_repo: SQLLeadRepository):
    await lead_repo.create(
        Lead(name="Juan Perez", email="juan@example.com", customer_type="consumer", message="Hi")
    )
    await lead_repo.create(
        Lead(name="Maria Lopez", email="maria@example.com", customer_type="consumer", message="Hi")
    )

    leads, total = await lead_repo.list(q="juan", read=None, customer_type=None, page=1, page_size=20)
    assert total == 1
    assert leads[0].name == "Juan Perez"


@pytest.mark.asyncio
async def test_list_pagination(lead_repo: SQLLeadRepository):
    for i in range(10):
        await lead_repo.create(
            Lead(
                name=f"User {i}",
                email=f"user{i}@example.com",
                customer_type="consumer",
                message="Hi",
            )
        )

    page1, total = await lead_repo.list(q=None, read=None, customer_type=None, page=1, page_size=3)
    assert len(page1) == 3
    assert total == 10

    page2, _ = await lead_repo.list(q=None, read=None, customer_type=None, page=2, page_size=3)
    assert len(page2) == 3


# ─── Set read ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_read_true(lead_repo: SQLLeadRepository):
    lead = Lead(
        name="Test", email="t@b.com", customer_type="consumer", message="Hi"
    )
    created = await lead_repo.create(lead)

    updated = await lead_repo.set_read(created.id, True)
    assert updated is not None
    assert updated.read is True


@pytest.mark.asyncio
async def test_set_read_on_nonexistent_returns_none(lead_repo: SQLLeadRepository):
    result = await lead_repo.set_read("nonexistent", True)
    assert result is None


# ─── Mark all read ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_all_read(lead_repo: SQLLeadRepository):
    for i in range(3):
        await lead_repo.create(
            Lead(name=f"User {i}", email=f"u{i}@b.com", customer_type="consumer", message="Hi")
        )

    count = await lead_repo.mark_all_read()
    assert count == 3

    leads, _ = await lead_repo.list(q=None, read=False, customer_type=None, page=1, page_size=20)
    assert len(leads) == 0


@pytest.mark.asyncio
async def test_mark_all_read_partial(lead_repo: SQLLeadRepository):
    await lead_repo.create(
        Lead(name="A", email="a@b.com", customer_type="consumer", message="Hi")
    )
    await lead_repo.create(
        Lead(name="B", email="b@b.com", customer_type="consumer", message="Hi")
    )

    # Mark one as read first
    leads, _ = await lead_repo.list(None, None, None, 1, 20)
    if leads:
        await lead_repo.set_read(leads[0].id, True)

    count = await lead_repo.mark_all_read()
    assert count == 1  # Only the unread one

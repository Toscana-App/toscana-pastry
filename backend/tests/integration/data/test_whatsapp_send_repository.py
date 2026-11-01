"""Integration tests for the WhatsAppSend repository (RF-P10-07/08, C7).

Covers create/get round-trip, list filters (status, from/to, pagination,
sent_at desc order), stats aggregation and count_provider_since (budget
RNF-P10-06).
"""

import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data.models import Base
from data.repositories.sql_whatsapp_send_repository import (
    SQLWhatsAppSendRepository,
)
from domain.whatsapp_send import WhatsAppSend

NOW = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.UTC)


@pytest_asyncio.fixture
async def send_repo(db_session) -> SQLWhatsAppSendRepository:
    return SQLWhatsAppSendRepository(db_session)


def make_send(status="sent", provider="business_api", sent_at=NOW, **kw):
    base = {
        "provider": provider,
        "phone": "+5491122334455",
        "message": "Hola",
        "reference_kind": "order",
        "reference_id": "o1",
        "sent_at": sent_at,
        "status": status,
    }
    base.update(kw)
    return WhatsAppSend(**base)  # type: ignore[arg-type]


# ─── Create / Get ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_get_roundtrip(send_repo):
    send = make_send()
    await send_repo.create(send)

    fetched = await send_repo.get(send.id)
    assert fetched is not None
    assert fetched.id == send.id
    assert fetched.provider == "business_api"
    assert fetched.status == "sent"
    assert fetched.sent_at == NOW


@pytest.mark.asyncio
async def test_get_unknown_returns_none(send_repo):
    assert await send_repo.get("no-existe") is None


@pytest.mark.asyncio
async def test_update_persists_state_change(send_repo):
    from domain.whatsapp_send import apply_status

    send = make_send()
    await send_repo.create(send)

    updated = apply_status(send, "read", now=NOW)
    await send_repo.update(updated)

    fetched = await send_repo.get(send.id)
    assert fetched is not None
    assert fetched.status == "read"
    assert fetched.read_at == NOW


# ─── List filters ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_filters_by_status(send_repo):
    await send_repo.create(make_send(status="sent", reference_id="o1"))
    failed = make_send(status="failed", reference_id="o2", failed_reason="expired")
    await send_repo.create(failed)
    await send_repo.create(make_send(status="read", reference_id="o3"))

    items, total = await send_repo.list(status="failed", page=1, page_size=50)
    assert total == 1
    assert items[0].reference_id == "o2"
    assert items[0].failed_reason == "expired"


@pytest.mark.asyncio
async def test_list_filters_by_time_range(send_repo):
    early = make_send(reference_id="o1", sent_at=NOW - datetime.timedelta(days=40))
    recent = make_send(reference_id="o2", sent_at=NOW)
    await send_repo.create(early)
    await send_repo.create(recent)

    since = NOW - datetime.timedelta(days=30)
    items, total = await send_repo.list(from_=since, to=NOW, page=1, page_size=50)
    assert total == 1
    assert items[0].reference_id == "o2"


@pytest.mark.asyncio
async def test_list_pagination_and_desc_order(send_repo):
    for i in range(5):
        await send_repo.create(
            make_send(
                reference_id=f"o{i}",
                sent_at=NOW - datetime.timedelta(minutes=i),
            )
        )

    page1, total = await send_repo.list(page=1, page_size=3)
    assert total == 5
    assert len(page1) == 3
    # orden desc por sent_at: el mas reciente primero
    assert page1[0].reference_id == "o0"
    assert page1[2].reference_id == "o2"

    page2, _ = await send_repo.list(page=2, page_size=3)
    assert [item.reference_id for item in page2] == ["o3", "o4"]


# ─── Stats ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_counts_by_status_in_window(send_repo):
    await send_repo.create(make_send(status="sent", reference_id="o1"))
    await send_repo.create(make_send(status="delivered", reference_id="o2"))
    await send_repo.create(make_send(status="read", reference_id="o3"))
    failed = make_send(status="failed", reference_id="o4", failed_reason="x")
    await send_repo.create(failed)
    # fuera de la ventana (40 dias atras): no cuenta
    old = make_send(reference_id="o5", sent_at=NOW - datetime.timedelta(days=40))
    await send_repo.create(old)

    stats = await send_repo.stats(window_days=30)
    assert stats["total"] == 4
    assert stats["sent"] == 1
    assert stats["delivered"] == 1
    assert stats["read"] == 1
    assert stats["failed"] == 1


@pytest.mark.asyncio
async def test_stats_empty(send_repo):
    stats = await send_repo.stats(window_days=30)
    assert stats == {
        "total": 0,
        "sent": 0,
        "delivered": 0,
        "read": 0,
        "failed": 0,
    }


# ─── Budget (RNF-P10-06) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_count_provider_since_counts_only_today_business(send_repo):
    await send_repo.create(make_send(provider="business_api", reference_id="b1"))
    await send_repo.create(make_send(provider="business_api", reference_id="b2"))
    # wa_me no cuenta contra el budget de business api
    await send_repo.create(make_send(provider="wa_me", reference_id="w1"))
    # business_api de ayer no cuenta
    yesterday = NOW - datetime.timedelta(days=1)
    await send_repo.create(make_send(reference_id="b3", sent_at=yesterday))

    count = await send_repo.count_provider_since(
        provider="business_api", since=NOW.replace(hour=0, minute=0, second=0)
    )
    assert count == 2

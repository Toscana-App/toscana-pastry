"""Integration tests for the WhatsApp sends API (RF-P10-07/08, C7).

Covers:
    GET /api/v1/whatsapp/sends:
        - 401 sin token, 403 para no-admin
        - 200 listado con filtros ?status, ?from, ?to y paginacion
    GET /api/v1/whatsapp/sends/stats:
        - 200 {total, sent, delivered, read, failed, read_rate}
    POST /api/v1/whatsapp/sends/{id}/resend:
        - 200 reintento exitoso (failed + business_api) → reset a sent
        - 409 si no es failed o el provider es wa_me
        - 404 si no existe
        - 429 si supera el budget diario (RNF-P10-06)
"""

import datetime
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.v1.auth.dependencies import get_user_repository
from api.v1.dependencies import require_admin
from api.v1.whatsapp.dependencies import (
    get_whatsapp_provider,
    get_whatsapp_send_repository,
)
from data.db import get_db as get_db_orig
from data.models import Base
from data.repositories.sql_user_repository import SQLUserRepository
from data.repositories.sql_whatsapp_send_repository import (
    SQLWhatsAppSendRepository,
)
from domain.models import User, UserRole
from domain.whatsapp_provider import MockBusinessApiProvider
from domain.whatsapp_send import WhatsAppSend
from main import app

NOW = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.UTC)


# ─── Fixtures ─────────────────────────────────────────────────────────


async def _admin_user():
    return User(email="admin@example.com", role=UserRole.ADMIN)


async def _customer_user():
    return User(email="customer@example.com", role=UserRole.CUSTOMER)


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_send_repo():
        yield SQLWhatsAppSendRepository(db_session)

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_whatsapp_send_repository] = override_get_send_repo
    app.dependency_overrides[require_admin] = _admin_user
    app.dependency_overrides[get_whatsapp_provider] = lambda: MockBusinessApiProvider()

    admin = User(email="admin@example.com", role=UserRole.ADMIN)
    await SQLUserRepository(db_session).save(admin)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def no_admin_client(db_session):
    """Client donde require_admin NO esta sobrepuesto (rol cliente)."""

    async def override_get_db():
        yield db_session

    async def override_get_user_repository():
        yield SQLUserRepository(db_session)

    async def override_get_send_repo():
        yield SQLWhatsAppSendRepository(db_session)

    app.dependency_overrides[get_db_orig] = override_get_db
    app.dependency_overrides[get_user_repository] = override_get_user_repository
    app.dependency_overrides[get_whatsapp_send_repository] = override_get_send_repo
    # NO sobrepone require_admin -> usa get_current_user real
    app.dependency_overrides[get_whatsapp_provider] = lambda: MockBusinessApiProvider()

    for user in (
        User(email="admin@example.com", role=UserRole.ADMIN),
        User(email="customer@example.com", role=UserRole.CUSTOMER),
    ):
        await SQLUserRepository(db_session).save(user)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ax:
            yield ax
    finally:
        app.dependency_overrides.clear()


def _make_send(**kw) -> WhatsAppSend:
    base = {
        "provider": "business_api",
        "phone": "+5491122334455",
        "message": "Hola, tu presupuesto",
        "reference_kind": "order",
        "reference_id": "o1",
        "sent_at": NOW,
        "status": "sent",
    }
    base.update(kw)
    return WhatsAppSend(**base)  # type: ignore[arg-type]


async def _seed(db_session, send: WhatsAppSend) -> str:
    repo = SQLWhatsAppSendRepository(db_session)
    await repo.create(send)
    return send.id


# ─── GET /sends: auth ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sends_requires_auth(no_admin_client):
    response = await no_admin_client.get("/api/v1/whatsapp/sends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_sends_forbidden_for_customer(no_admin_client):
    login = await no_admin_client.post(
        "/api/v1/auth/login", json={"email": "customer@example.com"}
    )
    token = login.json()["access_token"]
    response = await no_admin_client.get(
        "/api/v1/whatsapp/sends",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ─── GET /sends: list + filters ───────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sends_empty(client, db_session):
    response = await client.get("/api/v1/whatsapp/sends")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_sends_returns_items(client, db_session):
    await _seed(db_session, _make_send(reference_id="o1"))
    await _seed(
        db_session,
        _make_send(status="failed", reference_id="o2", failed_reason="expired"),
    )

    response = await client.get("/api/v1/whatsapp/sends")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["reference_id"] for item in body["items"]} == {"o1", "o2"}


@pytest.mark.asyncio
async def test_list_sends_filters_by_status(client, db_session):
    await _seed(db_session, _make_send(reference_id="o1"))
    await _seed(
        db_session,
        _make_send(status="failed", reference_id="o2", failed_reason="x"),
    )

    response = await client.get("/api/v1/whatsapp/sends", params={"status": "failed"})
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["reference_id"] == "o2"
    assert body["items"][0]["failed_reason"] == "x"


@pytest.mark.asyncio
async def test_list_sends_filters_by_time(client, db_session):
    await _seed(
        db_session,
        _make_send(reference_id="old", sent_at=NOW - datetime.timedelta(days=40)),
    )
    await _seed(db_session, _make_send(reference_id="recent"))

    response = await client.get(
        "/api/v1/whatsapp/sends",
        params={"from": (NOW - datetime.timedelta(days=30)).isoformat()},
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["reference_id"] == "recent"


@pytest.mark.asyncio
async def test_list_sends_invalid_status_422(client):
    response = await client.get("/api/v1/whatsapp/sends", params={"status": "bogus"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_sends_pagination(client, db_session):
    for i in range(5):
        await _seed(
            db_session,
            _make_send(
                reference_id=f"o{i}",
                sent_at=NOW - datetime.timedelta(minutes=i),
            ),
        )
    response = await client.get(
        "/api/v1/whatsapp/sends", params={"page": 2, "page_size": 3}
    )
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ─── GET /sends/stats ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_empty(client):
    response = await client.get("/api/v1/whatsapp/sends/stats")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "total": 0,
        "sent": 0,
        "delivered": 0,
        "read": 0,
        "failed": 0,
        "read_rate": 0.0,
    }


@pytest.mark.asyncio
async def test_stats_counts_and_read_rate(client, db_session):
    await _seed(db_session, _make_send(reference_id="o1"))  # sent
    await _seed(
        db_session,
        _make_send(status="delivered", reference_id="o2"),
    )
    await _seed(db_session, _make_send(status="read", reference_id="o3"))
    await _seed(
        db_session,
        _make_send(status="failed", reference_id="o4", failed_reason="x"),
    )

    response = await client.get("/api/v1/whatsapp/sends/stats")
    body = response.json()
    assert body["total"] == 4
    assert body["sent"] == 1
    assert body["delivered"] == 1
    assert body["read"] == 1
    assert body["failed"] == 1
    assert body["read_rate"] == pytest.approx(0.25)


# ─── POST /sends/{id}/resend ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_failed_business_api(client, db_session):
    send = _make_send(
        status="failed",
        reference_id="o1",
        failed_reason="expired",
        message_id="MOCK_OLD",
        delivered_at=NOW,
    )
    send_id = await _seed(db_session, send)

    response = await client.post(f"/api/v1/whatsapp/sends/{send_id}/resend")
    assert response.status_code == 200
    body = response.json()["send"]
    assert body["status"] == "sent"
    assert body["failed_reason"] is None
    assert body["delivered_at"] is None
    assert body["message_id"] is not None
    assert body["message_id"] != "MOCK_OLD"


@pytest.mark.asyncio
async def test_resend_not_failed_is_409(client, db_session):
    send = _make_send(reference_id="o1")  # status=sent
    send_id = await _seed(db_session, send)

    response = await client.post(f"/api/v1/whatsapp/sends/{send_id}/resend")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_resend_wa_me_is_409(client, db_session):
    send = _make_send(
        provider="wa_me",
        status="failed",
        reference_id="o1",
        failed_reason="x",
    )
    send_id = await _seed(db_session, send)

    response = await client.post(f"/api/v1/whatsapp/sends/{send_id}/resend")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_resend_unknown_is_404(client):
    response = await client.post(f"/api/v1/whatsapp/sends/{uuid.uuid4()}/resend")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resend_budget_exceeded_is_429(client, db_session):
    # Satura el budget diario (500) con envios business_api de hoy.
    from domain.whatsapp_send import BUSINESS_API_DAILY_LIMIT

    repo = SQLWhatsAppSendRepository(db_session)
    # The router counts the daily budget on the REAL UTC day, so seed from
    # datetime.now(UTC), not the fixed NOW fixture (flakes after UTC midnight).
    today_start = datetime.datetime.now(datetime.UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for i in range(BUSINESS_API_DAILY_LIMIT):
        await repo.create(
            _make_send(
                reference_id=f"bulk{i}",
                sent_at=today_start + datetime.timedelta(minutes=i),
            )
        )

    # Un fallo mas para reintentar.
    failed = _make_send(status="failed", reference_id="retry", failed_reason="x")
    failed_id = await _seed(db_session, failed)

    response = await client.post(f"/api/v1/whatsapp/sends/{failed_id}/resend")
    assert response.status_code == 429

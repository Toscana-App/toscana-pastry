"""Integration tests for Leads API (RF-P11-13, C5).

Covers public POST /leads + admin GET /leads, PATCH /leads/{id}/read,
POST /leads/read-all.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from data.db import get_db
from api.v1.leads.dependencies import get_lead_repository

app = FastAPI()


@pytest_asyncio.fixture
async def client(db_session):
    """Test client with DB override."""

    async def override_get_db():
        yield db_session

    async def override_get_lead_repo():
        from data.repositories.sql_lead_repository import SQLLeadRepository
        return SQLLeadRepository(db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_lead_repository] = override_get_lead_repo

    # Import and include routers AFTER dependency overrides are set
    from api.v1.leads.router import router as leads_router
    app.include_router(leads_router, prefix="/api/v1")

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


# ─── Public POST /leads ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_consumer_lead(client: TestClient):
    response = client.post("/api/v1/leads", json={
        "name": "Juan Perez",
        "email": "juan@example.com",
        "customer_type": "consumer",
        "message": "Quiero info de tortas",
    })
    assert response.status_code == 202
    data = response.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_create_business_lead(client: TestClient):
    response = client.post("/api/v1/leads", json={
        "name": "Empresa SA",
        "email": "contacto@empresa.com",
        "customer_type": "business",
        "business_name": "Empresa SA",
        "message": "Pedido mayorista",
    })
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_create_lead_validates_required_fields(client: TestClient):
    response = client.post("/api/v1/leads", json={
        "name": "",
        "email": "a@b.com",
        "customer_type": "consumer",
        "message": "Hi",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_lead_validates_customer_type(client: TestClient):
    response = client.post("/api/v1/leads", json={
        "name": "User",
        "email": "a@b.com",
        "customer_type": "invalid",
        "message": "Hi",
    })
    assert response.status_code == 422


# ─── Admin endpoints (require auth) ──────────────────────────────────

# Note: These tests need a valid auth token. For now, they verify the
# endpoint structure. Full admin tests would require mocking get_current_user.

@pytest.mark.asyncio
async def test_list_leads_requires_admin(client: TestClient):
    """Without auth → 401."""
    response = client.get("/api/v1/leads")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_lead_read_requires_admin(client: TestClient):
    """Without auth → 401."""
    response = client.patch("/api/v1/leads/some-id/read", json={"read": True})
    assert response.status_code == 401

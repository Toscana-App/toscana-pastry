"""Router de leads (RF-P11-13, C5).

POST /leads — public (hCaptcha + rate limit placeholder).
Admin: GET /leads, PATCH /leads/{id}/read, POST /leads/read-all.
Namespace: /api/v1/leads.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.v1.dependencies import require_admin
from api.v1.leads.dependencies import get_lead_repository
from api.v1.leads.schemas import (
    LeadCreateRequest,
    LeadListResponse,
    LeadReadAllResponse,
    LeadReadPatch,
    LeadResponse,
)
from data.repositories.sql_lead_repository import SQLLeadRepository
from domain.lead import Lead
from domain.models import User

router = APIRouter(prefix="/leads", tags=["leads"])


def _response(lead: Lead) -> LeadResponse:
    return LeadResponse(
        id=lead.id,
        name=lead.name,
        email=lead.email,
        customer_type=lead.customer_type,  # type: ignore[arg-type]
        message=lead.message,
        phone=lead.phone,
        business_name=lead.business_name,
        location=lead.location,
        read=lead.read,
    )


# ─── POST /leads (public) ───────────────────────────────────────────

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_lead(
    body: LeadCreateRequest,
    repo: SQLLeadRepository = Depends(get_lead_repository),
):
    """POST /leads: captura publica de contacto (RF-P11-13).

    hCaptcha + rate limit pendientes de implementacion en el gateway.
    Por ahora, valida el cuerpo y persiste.
    """
    lead = Lead(
        name=body.name.strip(),
        email=body.email.strip(),
        customer_type=body.customer_type,  # type: ignore[arg-type]
        message=body.message.strip(),
        phone=body.phone,
        business_name=body.business_name,
        location=body.location,
    )

    created = await repo.create(lead)
    return {"id": created.id}


# ─── Admin endpoints ─────────────────────────────────────────────────

@router.get("", response_model=LeadListResponse)
async def list_leads(
    q: str | None = Query(default=None, min_length=1, max_length=120),
    read: bool | None = Query(default=None),
    customer_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    repo: SQLLeadRepository = Depends(get_lead_repository),
    _admin: User = Depends(require_admin),
):
    """GET /leads: listado admin con ?q (name/email), ?read, ?customer_type."""
    items, total = await repo.list(q, read, customer_type, page, page_size)
    return LeadListResponse(
        items=[_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{id}/read", response_model=LeadResponse)
async def patch_lead_read(
    id: str,
    body: LeadReadPatch,
    repo: SQLLeadRepository = Depends(get_lead_repository),
    _admin: User = Depends(require_admin),
):
    """PATCH /leads/{id}/read: marca un lead como leido/no-leido."""
    lead = await repo.get(id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    updated = await repo.set_read(id, body.read)
    assert updated is not None  # DB should have the row
    return _response(updated)


@router.post("/read-all", response_model=LeadReadAllResponse)
async def mark_all_read(
    repo: SQLLeadRepository = Depends(get_lead_repository),
    _admin: User = Depends(require_admin),
):
    """POST /leads/read-all: marca todos los leads como leidos."""
    count = await repo.mark_all_read()
    return LeadReadAllResponse(updated=count)

"""PDF de presupuestos (Fase 8, P9).

- GET  /budgets/{id}/pdf  : PDF binario (autenticado). Cache por hash de
  contenido: la primera llamada genera y almacena; presupuesto editado →
  hash nuevo → regenera.
- POST /budgets/{id}/pdf  : link temporal firmado de 72 h (admin).
- GET  /pdf/{token}       : acceso público con token (sin sesión).

Seguridad: el documento renderizado no contiene costos ni margen — el
builder (domain/pdf.py) solo toca el snapshot del cliente, y la suite de
tests lo verifica contra el PDF real.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.v1.budgets.dependencies import get_budget_repository
from api.v1.dependencies import get_current_user, require_admin
from api.v1.pdf.dependencies import get_document_repository
from api.v1.pdf.schemas import PdfShareResponse
from api.v1.pdf.signing import make_share_token, verify_share_token
from api.v1.settings.dependencies import get_settings_repository
from core.config import settings as app_settings
from domain.budgets import Budget
from domain.models import User
from domain.pdf import budget_content_hash, build_budget_pdf
from domain.repositories import BudgetRepository, DocumentRepository, SettingsRepository
from domain.use_cases import GetSettings

router = APIRouter(tags=["pdf"])

PDF_MEDIA_TYPE = "application/pdf"


async def _pdf_for_budget(
    budget_repo: BudgetRepository,
    document_repo: DocumentRepository,
    settings_repo: SettingsRepository,
    budget_id: str,
) -> tuple[bytes, str, Budget]:
    """Obtén o genera el PDF con cache por hash de contenido (P9)."""
    budget = await budget_repo.get(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    settings = await GetSettings(settings_repo).execute()
    business = settings.business_name or ""
    footer = settings.footer_text or ""
    content_hash = budget_content_hash(budget, business, footer)
    cached = await document_repo.get(budget_id, content_hash)
    if cached is not None:
        return cached, content_hash, budget
    pdf = build_budget_pdf(budget, business, footer)
    await document_repo.save(budget_id, content_hash, pdf)
    return pdf, content_hash, budget


def _pdf_response(pdf: bytes, content_hash: str, seq: str, disposition: str) -> Response:
    etag = f'"{content_hash}"'
    filename = f"presupuesto_{seq.lstrip('#')}.pdf"
    return Response(
        content=pdf,
        media_type=PDF_MEDIA_TYPE,
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=0, must-revalidate",
            "Content-Disposition": f"{disposition}; filename=\"{filename}\"",
        },
    )


@router.get("/budgets/{budget_id}/pdf")
async def get_budget_pdf(
    budget_id: str,
    request: Request,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    """PDF server-side (P9): application/pdf con ETag por hash de
    contenido (304 si no cambió)."""
    pdf, content_hash, budget = await _pdf_for_budget(
        budget_repo, document_repo, settings_repo, budget_id
    )
    etag = f'"{content_hash}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    return _pdf_response(pdf, content_hash, budget.seq, disposition="attachment")


@router.post("/budgets/{budget_id}/pdf", response_model=PdfShareResponse)
async def share_budget_pdf(
    budget_id: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    _admin: User = Depends(require_admin),
):
    """Link temporal firmado (P9): 72 h, sin estado (HMAC), sin sesión.
    El cliente lo abre en el navegador del cliente final."""
    budget = await budget_repo.get(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    token, expires = make_share_token(budget_id, app_settings.SECRET_KEY)
    url = f"{app_settings.PUBLIC_BASE_URL}/api/v1/pdf/{token}"
    return PdfShareResponse(
        url=url,
        expires_at=datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
    )


@router.get("/pdf/{token}")
async def get_shared_pdf(
    token: str,
    budget_repo: BudgetRepository = Depends(get_budget_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Acceso público con token firmado (sin autenticación). Token
    vencido o alterado → 404 genérico (no se revela el motivo: evita
    enumeración)."""
    budget_id = verify_share_token(token, app_settings.SECRET_KEY)
    if budget_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link inválido o expirado",
        )
    pdf, content_hash, budget = await _pdf_for_budget(
        budget_repo, document_repo, settings_repo, budget_id
    )
    return _pdf_response(pdf, content_hash, budget.seq, disposition="inline")

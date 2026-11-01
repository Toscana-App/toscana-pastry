from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import require_admin
from api.v1.money import cents_to_decimal
from api.v1.settings.dependencies import get_settings_repository
from api.v1.pricing.schemas import PreviewRequest, PreviewResponse
from domain.models import User
from domain.pricing import UnitConversionError, calculate_price
from domain.repositories import SettingsRepository
from domain.use_cases import GetSettings

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/preview", response_model=PreviewResponse)
async def preview(
    payload: PreviewRequest,
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    # El preview expone el desglose de costos: herramienta de administracion.
    _admin: User = Depends(require_admin),
):
    """Carga el producto sin guardarlo (spec p04 §4): el usuario edita en vivo
    y el motor aplica los settings persistidos."""
    settings = await GetSettings(settings_repo).execute()
    items = [
        (item.qty, item.unit, cents_to_decimal(item.price_per_purchase_unit), item.purchase_unit)
        for item in payload.line_items
    ]
    try:
        breakdown = calculate_price(items, payload.prep_minutes, settings.to_pricing())
    except (UnitConversionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return PreviewResponse(**breakdown.__dict__)

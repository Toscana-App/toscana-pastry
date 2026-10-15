from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import get_current_user
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
    current_user: User = Depends(get_current_user),
):
    """Carga el producto sin guardarlo (spec p04 §4): el usuario edita en vivo
    y el motor aplica los settings persistidos."""
    settings = await GetSettings(settings_repo).execute()
    items = [
        (item.qty, item.unit, item.price_per_purchase_unit, item.purchase_unit)
        for item in payload.line_items
    ]
    try:
        breakdown = calculate_price(items, payload.prep_minutes, settings.to_pricing())
    except (UnitConversionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return PreviewResponse(**breakdown.__dict__)

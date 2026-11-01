from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import require_admin, require_role
from api.v1.money import cents_to_decimal
from api.v1.settings.dependencies import get_settings_repository
from api.v1.pricing.schemas import AudiencePriceResponse, PreviewRequest, PreviewResponse
from domain.models import User, UserRole
from domain.pricing import UnitConversionError, calculate_price
from domain.pricing_service import AudienceForbiddenError, compute_dual_pricing
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return PreviewResponse(
        materials=breakdown.materials,
        waste=breakdown.waste,
        materials_con_merma=breakdown.materials_con_merma,
        labor=breakdown.labor,
        gas=breakdown.gas,
        base=breakdown.base,
        margin_pct=breakdown.margin_pct,
        final=breakdown.rounded,
        rounded=breakdown.rounded,
        audience="revendedores",
    )


@router.post("/preview/dual", response_model=PreviewResponse | AudiencePriceResponse)
async def preview_dual(
    payload: PreviewRequest,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.NEGOCIO, UserRole.CUSTOMER)),
    settings_repo: SettingsRepository = Depends(get_settings_repository),
):
    """Preview con precios duales por audiencia.

    - admin: puede solicitar ``revendedores`` o ``consumidor_final``.
    - negocio: siempre ``revendedores``.
    - cliente: siempre ``consumidor_final``.

    Solo admin recibe el desglose completo; negocio y cliente reciben
    ``{audience, price}`` para no filtrar costos ni el precio base.
    """
    settings = await GetSettings(settings_repo).execute()
    items = [
        (item.qty, item.unit, cents_to_decimal(item.price_per_purchase_unit), item.purchase_unit)
        for item in payload.line_items
    ]

    try:
        breakdown = compute_dual_pricing(
            items,
            payload.prep_minutes,
            settings,
            user.role,
            payload.audience,
        )
    except AudienceForbiddenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except (UnitConversionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if user.role != UserRole.ADMIN:
        return AudiencePriceResponse(
            audience=breakdown.audience, price=breakdown.rounded
        )

    return PreviewResponse(
        materials=breakdown.materials,
        waste=breakdown.waste,
        materials_con_merma=breakdown.materials_con_merma,
        labor=breakdown.labor,
        gas=breakdown.gas,
        base=breakdown.base,
        margin_pct=breakdown.margin_pct,
        final=breakdown.rounded,
        rounded=breakdown.rounded,
        audience=breakdown.audience,
    )

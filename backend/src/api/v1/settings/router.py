from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import get_current_user, require_admin
from api.v1.money import cents_to_decimal
from api.v1.settings.dependencies import get_settings_repository
from api.v1.settings.schemas import (
    AdminSettingsResponse,
    SettingsResponse,
    SettingsUpdate,
)
from domain.models import BusinessSettings, User, UserRole
from domain.repositories import SettingsRepository
from domain.use_cases import GetSettings, UpdateSettings

router = APIRouter(prefix="/tenant/settings", tags=["settings"])


@router.get("", response_model=AdminSettingsResponse | SettingsResponse)
async def get_settings(
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(require_admin),
):
    settings = await GetSettings(settings_repo).execute()
    if current_user.role == UserRole.ADMIN:
        return AdminSettingsResponse(**settings.__dict__)
    return SettingsResponse(**settings.__dict__)


@router.put("", response_model=AdminSettingsResponse)
async def put_settings(
    payload: SettingsUpdate,
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    _admin: User = Depends(require_admin),
):
    try:
        data = payload.model_dump()
        data["hourly_rate"] = cents_to_decimal(data["hourly_rate"])
        data["round_step"] = cents_to_decimal(data["round_step"])
        settings = BusinessSettings(**data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    saved = await UpdateSettings(settings_repo).execute(settings)
    return AdminSettingsResponse(**saved.__dict__)

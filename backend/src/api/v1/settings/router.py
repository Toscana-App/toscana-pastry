from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.dependencies import get_current_user, require_admin
from api.v1.settings.dependencies import get_settings_repository
from api.v1.settings.schemas import SettingsUpdate, SettingsResponse
from domain.models import BusinessSettings, User
from domain.repositories import SettingsRepository
from domain.use_cases import GetSettings, UpdateSettings

# El path es el del contrato (api_endpoints.md §FASE 1 y p05): los costos son
# configuracion del negocio, no un recurso suelto.
router = APIRouter(prefix="/tenant/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    current_user: User = Depends(get_current_user),
):
    settings = await GetSettings(settings_repo).execute()
    return SettingsResponse(**settings.__dict__)


@router.put("", response_model=SettingsResponse)
async def put_settings(
    payload: SettingsUpdate,
    settings_repo: SettingsRepository = Depends(get_settings_repository),
    # Escribir los costos y margenes del negocio es funcion de administracion:
    # un usuario con rol customer recibe 403, no un guardado exitoso.
    _admin: User = Depends(require_admin),
):
    try:
        settings = BusinessSettings(**payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    saved = await UpdateSettings(settings_repo).execute(settings)
    return SettingsResponse(**saved.__dict__)

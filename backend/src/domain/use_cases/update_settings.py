from domain.models import BusinessSettings
from domain.repositories import SettingsRepository


class UpdateSettings:
    """Persiste los parametros de precio. Los rangos ya estan validados por
    BusinessSettings al construirse (ValueError si algo esta fuera de rango)."""

    def __init__(self, repository: SettingsRepository):
        self._repository = repository

    async def execute(self, settings: BusinessSettings) -> BusinessSettings:
        return await self._repository.save(settings)

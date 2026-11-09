from domain.models import BusinessSettings
from domain.repositories import SettingsRepository


class UpdateSettings:

    def __init__(self, repository: SettingsRepository):
        self._repository = repository

    async def execute(self, settings: BusinessSettings) -> BusinessSettings:
        return await self._repository.save(settings)

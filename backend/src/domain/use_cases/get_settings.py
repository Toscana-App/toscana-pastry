from domain.models import BusinessSettings, DEFAULT_BUSINESS_SETTINGS
from domain.repositories import SettingsRepository


class GetSettings:

    def __init__(self, repository: SettingsRepository):
        self._repository = repository

    async def execute(self) -> BusinessSettings:
        return await self._repository.get() or DEFAULT_BUSINESS_SETTINGS
